# Processing pipelines

What the script jobs (`job_scripts/release_jobs.py <job>`) and the plugin-side helpers do.
All script jobs read `.scripts/release_config.json` and write into
`$JOBSET_OUTPUT_WORK_PATH` (see [kicad-integration.md](kicad-integration.md)).

## Per-layer export (`layers`)

One file per selected layer and per ticked format. Gerbers are not part of this job: they
are a native jobset job (`pcb_gerbers`).

![layers](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/layers.puml)

<sub>Source: [diagrams/layers.puml](diagrams/layers.puml)</sub>

Intermediate PDFs live in a temporary folder outside the work dir (KiCad copies the work
dir as is) and are deleted at the end of each layer.

## PDF inversion inside the board outline

Used for negative films (e.g. solder mask): inside the board, black and white are swapped;
outside, the page stays white. Internal cut-outs stay white.

![inversion](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/inversion.puml)

<sub>Source: [diagrams/inversion.puml](diagrams/inversion.puml)</sub>

Why it works this way:

- **Outline from pcbnew, not from the plotted PDF.** The board shape comes from KiCad's own
  outline builder, so arcs, notches and cut-outs are exact and there is no minimum size.
- **Direct coordinate mapping.** `kicad-cli pcb export pdf` (scale 1, no autocentering)
  plots board coordinates 1:1 on the page: 1 mm of board = 72/25.4 pt from the page's top
  left corner. With `--mirror`, x becomes `page width − x`.
- **Repaint, don't clip.** Every black drawing touching the board is redrawn in white with
  the same geometry. An item straddling the edge (castellated pad opening) is redrawn
  whole: its outside part lands on white paper anyway, so the result is exact.
  "Touching" is tested on the item's bounding box: 9 sample points against the board
  region, plus any board vertex inside the box (thin items crossing a notch).
- **Decor drawn on top.** The layer alone is inverted; the drawing layer and outline are
  plotted separately and overlaid unchanged, so they are never inverted by mistake.
- Rendering at low resolution may show a hairline seam where white is redrawn over black
  (anti-aliasing); the geometry is identical and a RIP prints none.

## Gerber extensions (`gerber_ext`)

Runs in the work dir of the Gerber outputs (`01_PCB_GRB` and the ZIP), right after the
native Gerber and drill jobs, so the ZIP contains the normalised names too.

![gerber-ext](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/gerber-ext.puml)

<sub>Source: [diagrams/gerber-ext.puml](diagrams/gerber-ext.puml)</sub>

Matching on the exact name after the `<project>-` prefix avoids false matches when the
project name contains a layer word ("laptop" vs "top"). An extension that only differs by
case (`.gbl` vs `.GBL`) is left as is: on case-insensitive file systems both are the same
file.

## Other script jobs

| Job | kicad-cli command(s) |
|---|---|
| `sch_pdf` | `sch export pdf [--black-and-white]` on the root schematic |
| `pcb_pdf` | `pcb export pdf --mode-multipage --include-border-title`, pages = selected layers present in the board + Edge.Cuts |
| `implantation` | `pcb export pdf --mode-single` twice: `F.Fab,Dwgs.User,Edge.Cuts` and mirrored `B.Fab,Dwgs.User,Edge.Cuts` |
| `drill_map` | none: `drill_map_pdf.py` parses the `.kicad_pcb` and draws vertical drill marks (0.1 mm, 0.01 mm stroke) at absolute coordinates on the board's page size, plus Ø4 mm F.Cu camera fiducials |

Black & white (`--black-and-white`) follows the colour mode of the Options tab, except
inverted layers which are always black & white.

## BOM fields discovery (plugin side)

![bom-fields](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/bom-fields.puml)

<sub>Source: [diagrams/bom-fields.puml](diagrams/bom-fields.puml)</sub>

The table order is the CSV column order; ticked rows become `fields_ordered` /
`fields_labels` of the native `sch_export_bom` job, "Group" rows become `fields_group_by`.
