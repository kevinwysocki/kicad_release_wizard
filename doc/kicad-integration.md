# KiCad integration notes

KiCad behaviours the design relies on, found while testing with KiCad 10.0.1
(`kicad-cli`, jobsets, `pcbnew` Python API). Keep them in mind before changing how jobs
are launched.

## `special_execute` jobs

![special-execute](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/special-execute.puml)

<sub>Source: [diagrams/special-execute.puml](diagrams/special-execute.puml)</sub>

| Behaviour | Consequence in the wizard |
|---|---|
| On Windows the command goes through `cmd.exe` with its double quotes escaped (`\"`): a quoted path is not recognised. | Commands contain **no quotes**: `<python> .scripts/release_jobs.py <job>`. The interpreter path must not contain spaces; on Windows its 8.3 short name is used (`platform_tools.command_path()`). All other settings go through `release_config.json`. |
| The working directory is the project folder. | The script path is relative: `.scripts/release_jobs.py`. |
| `${KIPRJMOD}` is not expanded in the command text (it is in output paths, and set in the environment). | Nothing in the commands depends on text variables. |
| `JOBSET_OUTPUT_WORK_PATH` is the folder where the output is being prepared; native jobs write there too, and KiCad copies or zips it afterwards. | Script jobs write there, so their files follow the same path as native ones and end up in the ZIP when relevant (e.g. normalised Gerber names). |
| With `record_output`, the job log file stays empty. | `record_output` is off; each script writes its own `<job>.log` in the work dir. |
| An output whose `only` list is empty runs every job. | `build_jobset()` drops outputs with no job. |
| Each output runs its jobs again in a fresh work dir. | `pcb_gerbers` / `pcb_drill` / `gerber_ext` run twice when both the GRB folder and the ZIP are produced. |
| `kicad-cli` occasionally crashed (segfault) during a job in 10.0.1; a re-run passed. | Nothing to do in the wizard; the live log shows the failure. |

## Plot placement

`kicad-cli pcb export pdf --mode-single` (scale 1) keeps board coordinates: a point at
(x, y) mm in the board is drawn at (x × 72/25.4, y × 72/25.4) pt from the page's top left
corner. With `--mirror`, x becomes `page width − x`. The PDF inversion maps the pcbnew
outline with exactly this rule (verified on rectangular, castellated, cut-out and mirrored
boards).

`--negative` exists but fills the board's bounding box plus a margin, losing the real shape
(notches, rounded corners, cut-outs), hence the custom inversion.

## `pcbnew` Python API

| API | Note |
|---|---|
| `BOARD.GetBoardPolygonOutlines()` | KiCad 10: `(outlines, aInferOutlineIfNecessary, …)`; KiCad 9: `(outlines, aErrorHandler=None, …)`. `board_outline.py` tries the KiCad 10 form, then the KiCad 9 one. |
| `pcbnew.LoadBoard()` | Used on the saved file (what `kicad-cli` plots), not on the board in memory. |
| `BOARD.Save()` | Hung in a standalone KiCad Python during tests (probably a hidden message box); the wizard never saves boards. |
| wxLog | KiCad's warnings (e.g. `Font 'X' not found; substituting …`) pop up as message boxes when a dialog runs: the plugin and `LoadBoard()` run under `wx.LogNull()`. |

## `kicad-cli` output

- Warnings (fonts, VRML models…) are printed by `kicad-cli`; the job scripts capture
  `stdout` + `stderr` together and only fail on the exit code.
- `RunLogDialog` reads `kicad-cli`'s output as UTF-8 and strips ANSI colour codes.
- Processes started by the plugin use `CREATE_NO_WINDOW` on Windows (no console flashing).

## Interpreter and tools discovery

![discovery](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/discovery.puml)

<sub>Source: [diagrams/discovery.puml](diagrams/discovery.puml)</sub>

PyMuPDF is required only when the drill map, a PDF inversion or a PDF rotation is
requested; *Generate* stops with the exact `pip install` command otherwise.

## Data files

### `kicad_release_profile.json` (project root)

UI state, saved on *Generate* or with *Save profile*.

```json
{
  "version": 1,
  "project_name": "my_board",
  "jobs": { "erc": true, "drc": true, "sch_pdf": true, "pcb_pdf": true, "...": "..." },
  "layer_formats": ["gerber", "pdf"],
  "layers": [
    { "layer": "F.Mask", "export": true, "add_background": true, "add_edge_cuts": false,
      "invert_colors": true, "rotate_180": false, "mirror": false }
  ],
  "bom_fields": [
    { "field": "${ITEM_NUMBER}", "include": true, "label": "#", "group_by": false },
    { "field": "Value", "include": true, "label": "Value", "group_by": true }
  ],
  "options": { "color_mode": "color" }
}
```

### `.scripts/release_config.json`

Settings of the job scripts, written on every *Generate*.

```json
{
  "root": "/path/to/project",
  "project": "my_board",
  "pcb": "/path/to/project/my_board.kicad_pcb",
  "sch": "/path/to/project/my_board.kicad_sch",
  "kicad_cli": "/usr/bin/kicad-cli",
  "color_mode": "color",
  "layers": ["F.Cu", "B.Cu", "F.Mask"],
  "layer_options": [ { "layer": "F.Mask", "add_background": true, "...": "..." } ],
  "layer_formats": ["gerber", "pdf"],
  "debug": false
}
```

`"debug": true` keeps the intermediate PDFs of the layer job (their folder is logged).

### `.scripts/board_outline.json`

Written only when a PDF layer is inverted. Board coordinates in mm, Y pointing down.

```json
{
  "units": "mm",
  "outlines": [
    { "outer": [[119.1, 93.55], [177.52, 93.55], "..."],
      "holes": [[[160.0, 98.0], [168.0, 98.0], "..."]] }
  ]
}
```
