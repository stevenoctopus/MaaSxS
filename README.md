# MaaSxS

Automation for the mobile game **Sword x Staff** (Android, on a PC emulator).
It plays Daily Dungeon runs (including farming weekly affection), the
Crucible of Hieromon, Split Mirage, Conquest, Arena and Material Realms, and
claims your daily quests,
starting from whatever screen the game is on,
and recovers if the game crashes or disconnects.

Built on [MaaFramework](https://github.com/MaaXYZ/MaaFramework), with the
[MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia) GUI.

## Setup (Windows)

### 1. Set up the emulator

1. Install **MuMu Player** (what MaaSxS is tested on). LDPlayer 9 also works.
2. In the emulator's settings, set the resolution to **720 x 1280, portrait
   (phone)**. This matters: every screen position MaaSxS uses is made at that
   size, so any other resolution will misclick.
3. Make sure ADB is on. MuMu has it on by default. In LDPlayer: Settings >
   Other settings > ADB debugging > Open local connection.
4. Don't set a screen lock (PIN or pattern) inside the emulator: MaaSxS can't
   unlock it.
5. Install Sword x Staff, set the game language to **English**, and log in
   once by hand.

Run one emulator at a time: with several open, MaaSxS may connect to the
wrong one.

### 2. Install MaaSxS

1. Download the latest `MaaSxS-win-x86_64-<version>.zip` from
   [Releases](https://github.com/stevenoctopus/MaaSxS/releases).
2. Extract it to a normal folder you own, e.g. `Documents\MaaSxS`. Not
   Program Files: MaaSxS saves its settings and logs in its own folder.
3. Run `MFAAvalonia.exe` (that's the MaaSxS GUI; other MaaFramework projects
   use the same name).

If Windows stops it:

- **"Windows protected your PC"** (SmartScreen): click *More info* > *Run anyway*.
- **Smart App Control** blocks it outright, because the app isn't code-signed.
  The only way around that is to turn Smart App Control off (Windows Security >
  App & browser control > Smart App Control settings). Note that Windows
  won't let you turn it back on afterwards without resetting Windows.
- **.NET is missing**: install the
  [.NET 10 Runtime](https://dotnet.microsoft.com/download/dotnet/10.0) for x64.

### 3. Run it

1. Start the emulator first.
2. In the GUI, pick the emulator under the connection settings (it is found
   automatically; MuMu shows up as `MuMuPlayer`).
3. Tick the tasks you want, choose their options, and press **Start**.
   Progress shows in the log panel.

The GUI should open in English. If it doesn't, change the language in its
settings. One sidebar label stays in Chinese; that comes from the GUI itself.

### Optional: start the emulator for you

In the GUI's settings you can give it the emulator's path so it starts the
emulator before running tasks and restarts it if the connection drops. For
MuMu, the path is `C:\Program Files\Netease\MuMuPlayer\nx_main\MuMuNxMain.exe`
with the launch argument `-v 0` (instance 0), and set the before-tasks action
to start the emulator.

## Tasks

| Task | Options | What it does |
|---|---|---|
| Daily Dungeon | Mode, Dungeon, Difficulty | Runs the chosen dungeon and difficulty. **Daily** (default): buys extra reward attempts with Dawnium (*Buy extra attempts*: 0, 1 or 2, default 2, per day: attempts already bought today count, and never past the game's daily limit), then runs and claims the rewards until no reward attempts are left. *Claim grade* (S, A or higher, B or higher, Any; default S): a run graded lower leaves without claiming, keeping the attempt, and runs again. **Affection**: reads this week's affection (claiming any tokens waiting), runs the dungeons needed to reach the weekly cap (+7 per run), checks again, and repeats until capped. Never claims dungeon rewards, so your reward attempts are kept. Stops if a whole batch earns nothing. |
| Crucible of Hieromon | Mode | **Once**: one run, then claim rewards (the daily); if you already played today, it only claims. Claimed rewards are recognised, so nothing is tapped twice. **All gifts**: reads today's damage track, runs until your highest damage today reaches the last gift box, then claims. **All rewards**: the same, up to the last reward. |
| Split Mirage | Mode | **Once**: one run, then claim rewards (the daily); if you already played today, it only claims. Claimed rewards are recognised, so nothing is tapped twice. **All gems**: reads today's reward track, runs until your best wave today reaches the last gem, then claims. **All rewards**: the same, up to the last reward. Endless Mode is never used. |
| Conquest | Runs | **Once** (the daily quest) or **Twice**. Never more than the attempts left today. |
| Arena | Tickets to buy, Tickets to use | Buys tickets with Dawnium first (*Tickets to buy*: 0 to 8 per day, default 0; tickets already bought today count, and never past the game's daily limit), then challenges the rightmost opponent once per ticket (*Tickets to use*: default 2, any number), never more than the tickets you have. |
| Material Realms | Sets to buy, Tools to use (each per realm) | Buys tool sets on each realm's page first (*Sets to buy*: 0 to 20 sets of 5 per realm per day, default 0; sets already bought today count, and never past the daily limit), then uses tools in each realm (*Tools to use*: a number or ALL, default ALL). Realms with nothing to buy and no tools (no count badge on the list) aren't opened. ALL turns on Quick Mine / Quick Conquer and uses every tool; a number turns it off and uses exactly that many. |
| Vendor Booth | General: refreshes, General: buy items, Vault items (8) | Opens the cart on Home. **General**: buys each of the 9 items (gold) that's at least the chosen discount (*buy items*: Always, or 10% to 60% off or more; default Always), then refreshes and buys again (*refreshes*: 0 to 10 per day, default 0; refreshes already used today count). **Vault**: always claims the Free reward, and buys each item set to Buy (default Skip; Destiny Fruit buys both). Items that change daily (row 2 left and middle, row 3 left and middle) are set by position. |
| Claim daily quests | | Opens the daily quest list and claims every finished quest. Runs last, so it picks up what the other tasks completed. |

Every task:

- **Starts from any screen.** It finds its way from wherever the game is.
- **Retries once.** If something unexpected goes wrong, it goes back Home and
  starts the task over. If it fails again, it stops.
- **Stops the run for things only you can fix.** Not enough Dawnium or gold for
  what the options ask, or a safety stop (Daily Dungeon runs that don't claim,
  Affection runs that earn nothing): it logs `Stopped: <reason>`, doesn't retry,
  and the remaining tasks don't run either.
- **Recovers from crashes and disconnects.** If the game closed or went back to
  its start-up screens, it relaunches the game, gets through the Notice and
  "Tap to Play", and carries on.

Only dungeons shown on the Daily Dungeon list without scrolling are supported
so far.

## Troubleshooting

- **Taps land in the wrong place**: check the emulator resolution is
  720 x 1280 portrait.
- **It can't find the emulator**: start the emulator before the GUI, close
  any other emulators, and check ADB is on.
- **Anything else**: open an issue with the logs (the `logs` and `debug`
  folders next to `MFAAvalonia.exe`) and a screenshot of where it got stuck.

## Development

```
git clone --recursive git@github.com:stevenoctopus/MaaSxS.git
python -m pip install maafw -r tools/requirements.txt
python tools/configure.py          # copies the OCR model from MaaCommonAssets
```

- `assets/interface.json`: tasks and options shown in the GUI.
- `assets/resource/pipeline/`: the screen-by-screen logic.
  - `screens.json`: screen checks, defined once and referenced by name.
  - `common.json`: shared routines: get to the tab bar or Home from anywhere
    (including crash recovery), go to the Journal (`Common_ToJournal`, used
    by every Journal task), matchmaking, retry.
  - `purchase.json` and `track.json`: the Purchase popup and reward-track
    nodes, beside `agent/purchase.py` and `agent/track.py`.
  - one file per task, plus `affection.json` for the affection check.
- `agent/`: Python custom actions (loops, reading numbers), registered with
  `@AgentServer.custom_action` (a new task module also needs an import in
  `main.py`; the tests catch a missing one). `screen.py` reads the screen
  (hits, numbers, "N/M"). `common.py` holds the run loop every "run N
  times" task uses and reads a task's settings (see Settings node in
  GLOSSARY.md). `purchase.py` handles the Purchase popup (Arena, Daily Dungeon, Material Realms). `track.py` holds the reward-track logic
  shared by Crucible and Split Mirage. `badge.py` straightens the Vendor
  Booth's tilted discount badges so OCR can read them (numpy only).

Dev tools:

| Command | What it does |
|---|---|
| `python tools/run.py <task or node> [--opt "Option=Case"] [--opt "InputOption=value"] [--override <json>]` | runs a task, or any pipeline node, without the GUI. The agent starts through AgentClient, the same way the GUI does it |
| `python tools/screenshot.py [name]` | saves `debug/screenshots/<name>.png` at 720p |
| `python tools/ocr_dump.py live` or `<png> [x y w h]` | prints everything OCR reads, with boxes |
| `python tools/watch.py <session> [--seconds N] [--until REGEX]` | records every screen change with OCR text, for mapping new screens |
| `python -m unittest discover tests` | checks what the agent reads off saved game screens (discounts, reward tracks, tool badges, ...), that recovery knows every saved screen, and that interface.json matches the pipeline, about 35 s, no emulator needed |
| `python tools/still.py capture <name>` | saves the emulator's screen to `tests/screens/<name>.png` for a new test |

`tests/test_screens.py` shows each screenshot in `tests/screens/` to the
agent's own functions through `tools/still.py`: a stand-in device that
always shows that image and ignores taps. When the game changes a screen,
capture it again and update the expected values.

`tests/test_interface.py` checks that every task entry, option and node an
option changes exists, every `{placeholder}` is one of its option's inputs,
input defaults pass their own check, and every Custom action in the
pipeline is registered by the agent.

`tests/test_recovery.py` checks that the four recovery stages in
`common.json` look for the same screens, and that recovery recognises every
screenshot in `tests/screens/`. A new task needs no test changes; if a new
screenshot fails, add its screen to `Common_TabBar_BackOut` (when Android
back is safe there) or give it its own `Common_TabBar_*` step.

Flows (buying, refreshing, stopping for Dawnium) are tested live, not
offline: see `docs/adr/0001-buying-flows-are-tested-live.md`.

With several emulators running, set `MAASXS_DEVICE` (part of the device name
or address, e.g. `127.0.0.1:16384`) to choose one.

The game font sometimes merges words ("Riftwatch Fortress" reads as
`RiftwatchFortress`), so OCR patterns use `\s?` where a space may be lost.

### Local GUI build

1. Extract the MaaFramework release (`MAA-win-x86_64-*.zip`) into `deps/`.
2. Extract the MFAAvalonia release into `install/`, without its `runtimes/` folder.
3. `cd tools; python install.py v0.1.0 win x86_64` (close the GUI first: it locks its DLLs).
   On Windows this also puts an embedded Python 3.12 with `maafw` in `install/python/`
   and points the agent at it.
4. Run `install/MFAAvalonia.exe`.

Pushing a `v*` tag does all of this in CI and publishes a release.
Keep `MAAFW_VERSION` in `.github/workflows/install.yml` and `maafw` in
`agent/requirements.txt` on the same version.
