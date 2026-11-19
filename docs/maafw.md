# MaaFramework built-ins for MaaSxS

What MaaFramework 5.15 (the pinned `maafw`) does natively, and which agent
work it replaces. Write Python only for what these can't express (arithmetic,
numbers in log lines, state across screens), and say why in a comment.
"Verified" means checked in this repo on 5.15 (a saved-screen test or a probe);
the rest is from the [Pipeline Protocol](https://maafw.com/en/docs/3.1-PipelineProtocol/).

## Recognition

| Need | Built-in | Notes |
|---|---|---|
| Text, a number, "N/M" | `OCR` (`expected` regex, `roi`) | Patterns use `\s?` between words: the game font drops spaces. `screen.py` parses the numbers. |
| Coloured patches, several per screen | `ColorMatch`, `connected: true` | Verified: one result per connected patch, same boxes as OpenCV's connected components; `count` = the patch's pixel count, kept in `filtered_results`. `method` 4 = RGB (screenshots are BGR: reverse the channels), 40 = HSV (OpenCV scale, H 0-180): prefer HSV, which holds up better when rendering shifts colours. Example: `GrandMines_Bars`, `GrandMines_Links`. |
| An icon or shape | `TemplateMatch`, PNGs in `assets/resource/image/` | `green_mask: true` ignores pure green (0, 255, 0) pixels, for shapes whose inside changes. Every match above `threshold` is in `filtered_results`, each with its `score`. Verified slow with a mask on a big roi: 4 masked templates over 720x1100 took 4 s (vs 0.13 s in OpenCV). Fine for a check on a small roi; too slow for polling a whole screen. |
| Several conditions | `And` (`all_of`) / `Or` (`any_of`) | Reference other nodes by name; `box_index` picks whose box an action uses. |
| Wait for something to show | the node's own `timeout` (recognition retries until it) | Replaces a Python polling loop: `DailyDungeon_BuyShown`. |

Read every result in Python with `context.run_recognition(node, image)` and
`reco.filtered_results` (each has `box`, `score`, and `count` or `text`). The
binding has no image file I/O: screenshots are BGR numpy arrays, and the
agent saves PNGs with `snapshots.save_png`.

## Flow

- **Shared step**: a node with an action and no `next`, used as
  `"[JumpBack]<name>"` in a route: it runs, then the route looks again from the
  top of its own list. `Common_ToJournal`, `Common_TapToContinue`,
  `Common_Journal_DailyEvents`.
- **Screen checks in `next`**: reference `Screen_*` directly to end a route
  on a screen; a wrapper node only earns its place with a `focus` message
  (`DailyDungeon_BackOnList`, "Run complete").
- **`repeat` / `repeat_delay`**: one action N times (the Purchase popup's "+":
  `purchase.py` sets `repeat`). Must be at least 1.
- **`enabled: false`**: verified: skipped when it appears in a `next` list,
  but `run_recognition` still runs it. An option's case turns it on
  (`DailyDungeon_LowGrade`).
- **`max_hit`**: verified: counts last for the whole task (across
  `run_task` calls inside it) and reset with each new task;
  `context.clear_hit_count(node)` resets one.
- **`attach`**: verified: overrides merge into it key by key (resource,
  context and `run_task` overrides). How MFAAvalonia combines two options'
  overrides of one node is unverified, so options that set buy amounts keep
  their own Settings nodes (GLOSSARY.md).
- **Taps the agent places**: a `Click` node run with `context.run_action`
  and a `target` override (`GrandMines_Tap`), so the tap shows in
  MaaFramework's log.

## What stays in Python

- Numbers: daily totals, thresholds, "11.3B" (`purchase.py`, `crucible.py`).
  5.15 pipelines can't compare or count; 6.0's OCR `condition` will cover
  simple comparisons once it's stable.
- Log lines with values: `focus` messages can't include recognised text.
- Image work the nodes lack: rotation (`badge.py`), flat-floor detection
  (`grand_mines.find_floor`, numpy).
- Whole-screen searches polled many times a second: the flashing-icon ring
  search (`grand_mines.find_icons`, a masked normalised correlation with numpy
  FFTs, 0.5 s) replaced a TemplateMatch node that took 4 s and missed the icon
  after a link.

## Looking things up

- Protocol and API: the `maa-wiki` skill (Everything-Maa plugin), or
  https://maafw.com/en/docs/3.1-PipelineProtocol/. The installed binding's
  source, `install/python/Lib/site-packages/maa/`, is the exact version.
- Settling an undocumented behaviour: a throwaway probe through
  `tools/still.py` (`Still().run(screen, fn)` gives a real `Context` on a
  saved screen), then a line here.
