# Architecture

The wizard has two halves that never run at the same time:

1. **The plugin**, running inside the KiCad PCB editor (embedded Python, `pcbnew` + `wx`).
   It shows the dialog, saves the profile, and on *Generate* writes everything the export
   needs into the project folder: job scripts, their settings and a `.kicad_jobset`.
2. **The jobset run**, a separate `kicad-cli jobset run` process started by the plugin.
   KiCad runs its native jobs itself and calls the wizard's job scripts with the
   **system Python** for everything it cannot do natively.

The project folder is the only link between the two: once generated, the jobset can be
re-run without the plugin (`kicad-cli jobset run --file release/kicad_release.kicad_jobset <project>.kicad_pro`).

## Components

![components](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/components.puml)

<sub>Source: [diagrams/components.puml](diagrams/components.puml)</sub>

## Source tree

| Path | Runs in | Role |
|---|---|---|
| `__init__.py` | KiCad | Registers the action plugin |
| `action_release_wizard.py` | KiCad | Plugin entry point; silences KiCad's wxLog pop-ups while the dialog is open |
| `release_wizard_dialog.py` | KiCad | Dialog (Jobs / Layers / BOM / Options tabs), profile, `generate_files()`, `build_jobset()`, `RunLogDialog` |
| `bom_fields.py` | KiCad | Reads the `.kicad_sch` files to list the fields of placed symbols |
| `board_outline.py` | KiCad | Board outline polygons (with cut-outs) through `pcbnew` → `board_outline.json` |
| `platform_tools.py` | KiCad | Finds `kicad-cli` and a Python 3 interpreter; quote-free command paths |
| `i18n.py` | KiCad | French / English strings, language detection |
| `job_scripts/release_jobs.py` | System Python | Job runner: one sub-command per script step |
| `job_scripts/pdf_tools.py` | System Python | PDF inversion inside the board outline, 180° rotation (PyMuPDF) |
| `job_scripts/drill_map_pdf.py` | System Python | Vector drill map from the `.kicad_pcb` file (PyMuPDF) |
| `resources/` | — | Logo and its generator |

The plugin never imports `job_scripts/`: these files are copied to `<project>/.scripts/`
on every *Generate* and only run under the system Python.

## Generate sequence

![generate](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/generate.puml)

<sub>Source: [diagrams/generate.puml](diagrams/generate.puml)</sub>

## Jobset structure

`build_jobset()` only emits the jobs that are ticked, and an output only when at least one
of its jobs exists (an empty `only` list would make KiCad run every job).
Native jobs are configured in the jobset; *script* jobs are `special_execute` steps running
`<python> .scripts/release_jobs.py <job>`.

![jobset](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/jobset.puml)

<sub>Source: [diagrams/jobset.puml](diagrams/jobset.puml)</sub>

`01_PCB_LAYERS` exists only when PDF, SVG or DXF is ticked in the Layers tab; the Gerber
jobs and the `GERBER` ZIP only when the Gerber format is ticked (and the ZIP job for the
archive).

| Job id | Kind | Produces |
|---|---|---|
| `erc` | native `sch_erc` | `<project>_ERC.txt` |
| `drc` | native `pcb_drc` | `<project>_DRC.txt` (with schematic parity) |
| `sch_pdf` | script `sch_pdf` | `<project>_SCH.pdf` |
| `pcb_pdf` | script `pcb_pdf` | `<project>_PCB.pdf`, one page per selected layer + Edge.Cuts |
| `pcb_layers` | script `layers` | `PDF/`, `SVG/`, `DXF/<layer>.*`, one file per layer and format |
| `drill_map_pdf` | script `drill_map` | `PDF/<project>_DRILL_MAP.pdf` |
| `pcb_implantation` | script `implantation` | `<project>_IMPLANT_TOP.pdf`, `_IMPLANT_BOT.pdf` |
| `bom_csv` | native `sch_export_bom` | `<project>_BOM.csv` |
| `pnp_csv` | native `pcb_export_pos` | `<project>_POS*.csv` |
| `pcb_drill` | native `pcb_export_drill` | `<project>.drl` |
| `pcb_gerbers` | native `pcb_export_gerbers` | one Gerber per selected layer + Edge.Cuts, job file |
| `pcb_gerber_extensions` | script `gerber_ext` | renames Gerbers in the work dir, `.GKO` → `.GM1` copy |
| `meca_step` | native `pcb_export_3d` | `<project>_STEP.step` |

Script jobs write into `$JOBSET_OUTPUT_WORK_PATH`, like native jobs, so KiCad copies or
zips their files with the rest of the output. Each one also writes `<job>.log` there
(except `gerber_ext`, whose folder ends up in the fab ZIP).

## Plugin-side state

![dialog-state](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/dialog-state.puml)

<sub>Source: [diagrams/dialog-state.puml](diagrams/dialog-state.puml)</sub>

See also [pipelines.md](pipelines.md) for what each script job does and
[kicad-integration.md](kicad-integration.md) for the KiCad behaviours the design relies on.
