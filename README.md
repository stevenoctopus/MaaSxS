# MaaSxS

Automation for the mobile game **Sword x Staff** (Android, on a PC emulator).
It plays Daily Dungeon runs (including farming weekly affection) and the
Crucible of Hieromon for you, starting from whatever screen the game is on,
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
| Daily Dungeon | Mode, Dungeon, Difficulty | **Single run**: one run of the chosen dungeon and difficulty. **Affection**: reads this week's affection (claiming any tokens waiting), runs the dungeons needed to reach the weekly cap (+7 per run), checks again, and repeats until capped. Stops if a whole batch earns nothing. |
| Crucible of Hieromon | Mode | **Once**: one run, then claim rewards (the daily). **All gifts**: reads today's damage track, runs until your highest damage today reaches the last gift box, then claims. **All rewards**: the same, up to the last reward. |

Every task:

- **Starts from any screen.** It finds its way from wherever the game is.
- **Retries once.** If something goes wrong, it goes back Home and starts the
  task over. If it fails again, it stops.
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
    (including crash recovery), matchmaking, retry.
  - one file per task, plus `affection.json` for the affection check.
- `agent/`: Python custom actions (loops, reading numbers), registered with
  `@AgentServer.custom_action`.

Dev tools:

| Command | What it does |
|---|---|
| `python tools/run.py <task or node> [--opt "Option=Case"] [--override <json>]` | runs a task, or any pipeline node, without the GUI. The agent starts through AgentClient, the same way the GUI does it |
| `python tools/screenshot.py [name]` | saves `debug/screenshots/<name>.png` at 720p |
| `python tools/ocr_dump.py live` or `<png> [x y w h]` | prints everything OCR reads, with boxes |
| `python tools/watch.py <session> [--seconds N] [--until REGEX]` | records every screen change with OCR text, for mapping new screens |

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
