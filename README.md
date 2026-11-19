# KiCad Release Wizard

<img src="resources/logo_256.png" width="96" align="right" alt="logo">

KiCad action plugin (PCB editor) that builds a `.kicad_jobset` and runs
`kicad-cli jobset run` to export a complete release package from the schematic and
the board: ERC/DRC reports, schematic and PCB PDFs, per-layer Gerber / PDF / SVG / DXF,
assembly drawings, drill map, BOM, pick-and-place, drill files, Gerber ZIP and STEP.

Works on **Windows, macOS and Linux**.

## Dependencies

| Dependency | Version | Used for |
|---|---|---|
| [KiCad](https://www.kicad.org/) | 10.0+ | Host application, `kicad-cli` exports |
| [Python 3](https://www.python.org/) (system install) | 3.8+ | Job scripts copied to `<project>/.scripts/` |
| [PyMuPDF](https://pymupdf.readthedocs.io/) | 1.23+ | Drill map, PDF inversion and 180° rotation |

```
python3 -m pip install -r requirements.txt      # Windows: py -3 -m pip install -r requirements.txt
```

The plugin itself (running inside KiCad) only uses `pcbnew` and `wx`, both provided by KiCad.

On **Generate**, the plugin looks for:

- `kicad-cli`: next to the running KiCad first, then `PATH` and the usual install folders.
  Override with the `KICAD_CLI` environment variable.
- a Python 3 interpreter for the job scripts, preferring one with PyMuPDF: `py -3`, `python`,
  `python3` (Windows) or `python3`, `python` (macOS / Linux), then KiCad's bundled Python.
  Override with `KICAD_RELEASE_WIZARD_PYTHON`.

KiCad runs the script steps as `<python> .scripts/release_jobs.py <job>` from the project
folder. These commands cannot contain quotes, so the interpreter path must not contain
spaces (on Windows its 8.3 short name is used automatically).

## Usage

- **Jobs**: tick what to produce, grouped by theme; hover a checkbox for details (output
  file, folder, settings).

  | Group | Jobs |
  |---|---|
  | Design rules | ERC, DRC |
  | Schematic | Schematic PDF |
  | PCB layout | One file per layer, single PDF with all layers, assembly drawing |
  | Drilling | Drill map PDF (board outline and drawing sheet optional), Excellon drill file |
  | Bill of materials | BOM CSV |
  | Fabrication files | Pick and place CSV, Gerber + drill .zip |
  | Mechanical | 3D model (.step) |
- **Layers**: tick the layers to export and the formats produced by the *One file per layer*
  job, one file per layer and per format (click a checkbox column header to tick / untick the
  whole column):
  - **Gerber**: X2, coordinates 4.6 in mm, Edge.Cuts always included, normalised Protel
    extensions (also inside the ZIP), Gerber job file (`release/01_PCB/GRB`).
  - **PDF**: per-layer options apply: drawing sheet (frame and title block), outline (Edge.Cuts),
    mirror, black/white inversion inside the board outline, 180° rotation (`release/01_PCB/PDF`).
    The inversion uses the exact board outline read through pcbnew (internal cut-outs stay
    white, any board size); the drawing sheet stays as is and Edge.Cuts is drawn on top.
  - **SVG**: drawing sheet, outline and mirror apply (`release/01_PCB/SVG`).
  - **DXF**: drawing sheet and outline apply, mm, contours (`release/01_PCB/DXF`).

  The ticked layers are also the pages of the *Single PDF with all layers* job.
- **BOM**: the fields found in the project's symbols plus KiCad's generated fields
  (`${ITEM_NUMBER}`, `${QUANTITY}`…). Tick the columns, edit their labels, choose the grouping
  fields and reorder them with *Move up / Move down*: table order = CSV column order.
- **Options**: PDF/SVG rendering in colour (default layer colours) or black & white.

**Generate** writes the scripts and the jobset, then shows the `kicad-cli` output live.
The DRC can take minutes on large boards (it is KiCad's own DRC, as in the PCB editor).

Settings are saved to `kicad_release_profile.json` at the project root.

The UI is in French when the locale is French, English otherwise
(force it with `KICAD_RELEASE_WIZARD_LANG=fr` or `en`).

## Installation

Once listed in the KiCad Plugin and Content Manager, install it from there
(*Tools → Plugin and Content Manager*). Manual installation:

Copy (or clone) this folder into KiCad's plugin directory, then in the PCB editor:
*Tools → External Plugins → Refresh Plugins*.

| OS | Plugin directory |
|---|---|
| Windows | `%USERPROFILE%\Documents\KiCad\10.0\scripting\plugins\` |
| macOS | `~/Documents/KiCad/10.0/scripting/plugins/` |
| Linux | `~/.local/share/kicad/10.0/scripting/plugins/` |

## Output layout

```
release/
├── 01_PCB/GRB   Gerbers, drill, <project>-GERBER.zip
├── 01_PCB/PDF   per-layer PDFs, drill map
├── 01_PCB/SVG   per-layer SVGs
├── 01_PCB/DXF   per-layer DXFs
├── 02_PCBA      assembly drawings, BOM, pick-and-place
├── 03_DOCS      ERC, DRC, schematic PDF, PCB PDF
└── 04_MECA      STEP
```

All generated files are named `<project>-<LAYER or FUNCTION>`: `<project>-F_Cu.gtl`,
`<project>-F_Mask.pdf`, `<project>-PTH.drl`, `<project>-NPTH.drl`, `<project>-DRILL_MAP.pdf`, `<project>-BOM.csv`,
`<project>-POS.csv`, `<project>-ERC.txt`, `<project>-3D.step`, `<project>-GERBER.zip`…

## Project layout

Developer documentation (architecture, pipelines, KiCad integration notes, PlantUML
diagrams) is in [doc/](doc/README.md).

| Path | Role |
|---|---|
| `action_release_wizard.py` | KiCad action plugin entry point |
| `release_wizard_dialog.py` | Dialog, profile, jobset generation, live run log |
| `bom_fields.py` | Symbol fields discovery for the BOM tab |
| `board_outline.py` | Exact board outline (with cut-outs) through pcbnew |
| `platform_tools.py` | `kicad-cli` / Python discovery on Windows, macOS, Linux |
| `i18n.py` | French / English strings |
| `job_scripts/` | Scripts copied to `<project>/.scripts/` and run by the jobset |
| `pcm/` | KiCad Plugin and Content Manager packaging ([doc/release.md](doc/release.md)) |

## Logo

`resources/logo.png` (24×24 toolbar icon) and `resources/logo_256.png` are generated by
`python resources/make_logo.py` (requires Pillow).
