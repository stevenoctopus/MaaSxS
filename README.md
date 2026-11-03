# MaaSxS

Automation for the mobile game **Sword x Staff**, built on
[MaaFramework](https://github.com/MaaXYZ/MaaFramework) from the
[MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) template.
The GUI is [MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia).

## Requirements

- **The emulator must run at 720x1280 (portrait).** Every screen region and
  template image is made at that resolution, so other resolutions will misclick.
- ADB debugging enabled in the emulator (tested with LDPlayer 9).
- Python 3 with `maafw` (`pip install maafw`). The GUI starts `agent/main.py` with it.

## Tasks

| Task | Options | Starts on | Does |
|---|---|---|---|
| Daily Dungeon | Mode, Dungeon, Difficulty | Daily Dungeon list | **Single run**: Match, Accept, Ready, wait out the floors, leave results, back on the list. **Affection**: read this week's affection, run until the cap (+7 per run), recheck once and top up. |
| Check Affection | - | Daily Dungeon list, Journal or Home | Friends > Affection Tokens, claim, read the weekly total, return to the Daily Dungeon list. |

Only dungeons visible and unlocked on the list without scrolling are supported so far.
For testing use **Court of Purification on Nightmare**: its queue is much faster.

## Development

```
git clone --recursive git@github.com:stevenoctopus/MaaSxS.git
python -m pip install maafw -r tools/requirements.txt
python tools/configure.py          # copies the OCR model from MaaCommonAssets
```

- `assets/interface.json`: tasks and options shown in the GUI.
- `assets/resource/pipeline/`: the screen-by-screen logic.
- `agent/`: Python custom actions (loops, reading numbers), registered with `@AgentServer.custom_action`.

Dev tools:

| Command | What it does |
|---|---|
| `python tools/run.py <task> [--opt "Option=Case"] [--override <json>]` | runs a task without the GUI. The agent is started through AgentClient, the same way the GUI does it |
| `python tools/screenshot.py [name]` | saves `debug/screenshots/<name>.png` at 720p |
| `python tools/ocr_dump.py live` or `<png> [x y w h]` | prints everything OCR reads, with boxes |
| `python tools/watch.py <session> [--seconds N] [--until REGEX]` | records every screen change with OCR text, for mapping new screens |

The game font sometimes merges words ("Riftwatch Fortress" reads as
`RiftwatchFortress`), so OCR patterns use `\s?` where a space may be lost.

### Local GUI build

1. Extract the MaaFramework release (`MAA-win-x86_64-*.zip`) into `deps/`.
2. Extract the MFAAvalonia release into `install/`, without its `runtimes/` folder.
3. `cd tools; python install.py v0.1.0 win x86_64`
4. Run `install/MFAAvalonia.exe`.

Pushing a `v*` tag does all of this in CI and publishes a release.
MFAAvalonia is unsigned, so Windows Smart App Control blocks it.
