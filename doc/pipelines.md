# Processing pipelines

What the script jobs (`job_scripts/release_jobs.py <job>`) and the plugin-side helpers do.
All script jobs read `.scripts/release_config.json` and write into
`$JOBSET_OUTPUT_WORK_PATH` (see [kicad-integration.md](kicad-integration.md)).

## Per-layer export (`layers`)

One file per selected layer and per ticked format. Gerbers are not part of this job: they
are a native jobset job (`pcb_gerbers`).

![layers](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/layers.puml)

<sub>Source: [diagrams/layers.puml](diagrams/layers.puml)</sub>

**CMYK black** (Options tab, "Black of black & white PDFs" = CMYK): KiCad writes black &
white PDFs with RGB black (`0 0 0 rg` / `RG`) and, after an inversion, RGB white. In CMYK
mode `pdf_tools.to_cmyk_black()` rewrites these operators in the content streams of the
pages and form XObjects: neutral colours become DeviceCMYK with C=M=Y=0 and K = 1 − grey
level (black `0 0 0 1 k`, white `0 0 0 0 k`, the drill map's grey slots K 40 %). No colour
profile is involved, so editors read pure K instead of converting RGB black to a rich
four-colour black. Non-neutral colours are left untouched and logged. It applies to every
PDF in black & white mode, and in colour mode to the inverted layers and the drill map
(always black & white).

Every plot uses `--drill-shape-opt 0`: KiCad's default draws the drill holes on each
layer, which is not wanted in the layer files (the drill map shows the holes).

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
- **Drawing sheet and outline left alone.** The drawing sheet (frame and title block) is
  plotted with the layer, but drawings enclosing the whole board (the frame) are never
  repainted; the outline (Edge.Cuts) is plotted separately and drawn on top unchanged.
- Rendering at low resolution may show a hairline seam where white is redrawn over black
  (anti-aliasing); the geometry is identical and a RIP prints none.

## File names (`fix_names`)

Every generated file is named `<project>-<LAYER or FUNCTION>`. KiCad's native jobs mostly
follow that rule (`<project>-F_Cu.gtl`, `<project>-job.gbrjob`, `<project>-PTH.drl`);
`fix_names` runs last in the outputs holding Gerbers or position files (`01_PCB_GRB`, the Gerber ZIP, `02_PCBA`) and
fixes the rest in the work dir, so the ZIP contains the final names too.

![fix-names](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/fix-names.puml)

<sub>Source: [diagrams/fix-names.puml](diagrams/fix-names.puml)</sub>

- Gerber extensions: lower-case Protel extensions, as KiCad writes them (KiCad already uses
  them for the standard layers; inner power planes become `.gpN`). Matching on the exact
  name after the `<project>-` prefix avoids false matches when the project name contains a
  layer word ("laptop" vs "top").
- The board outline is renamed from KiCad's `.gm1` (Protel "Mechanical 1") to `.gko`
  (Protel / Altium "Keep-Out"), the board-outline extension fab houses list first. Only one
  outline file is delivered.
- Drill files need nothing: PTH and NPTH are separate files, `<project>-PTH.drl` and
  `<project>-NPTH.drl`, so non-plated holes cannot be plated by mistake.
- KiCad always appends `-all-pos` to the position file name: it is removed.
- The Gerber job file lists the Gerber file names: it is updated after the renames.

## Other script jobs

| Job | kicad-cli command(s) |
|---|---|
| `sch_pdf` | `sch export pdf [--black-and-white]` on the root schematic |
| `pcb_pdf` | `pcb export pdf --mode-multipage --include-border-title`, pages = selected layers present in the board + Edge.Cuts |
| `implantation` | `pcb export pdf --mode-single --include-border-title` twice: `F.Fab,Edge.Cuts` and mirrored `B.Fab,Edge.Cuts` |
| `drill_map` | see [Drill map](#drill-map-drill_map) below |

Black & white (`--black-and-white`) follows the colour mode of the Options tab, except
inverted layers which are always black & white.

## Drill map (`drill_map`)

Built from KiCad's own outputs, so the map always matches the fabrication drill files.

![drill-map](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/drill-map.puml)

<sub>Source: [diagrams/drill-map.puml](diagrams/drill-map.puml)</sub>

- **Holes**: parsed from the Excellon files (`T<n>C<diameter>` tools, `X…Y…` hits,
  `X…Y…G85X…Y…` slots, Y negated back to board coordinates). PTH / NPTH comes from the file
  function, vias from the `ViaDrill` tool attribute.
- **Groups**: one per (plated, diameter, hole or slot), plated first then by diameter; each
  group gets a symbol: `+`, `x`, circle, square, triangle, diamond, hexagon, inverted
  triangle, then the same outlines with `+` and `x` inside (20 symbols, reused beyond).
- **Symbols** are drawn at the hole centre, sized like the hole but kept between 0.6 and
  2.5 mm; slots are also drawn as a grey stadium of the slot width.
- **Drill table** at the top left (10 mm margins): symbol, diameter (mm), count, type
  (`PTH`, `PTH via`, `PTH slot`, `NPTH`…) and total. A warning is logged when it overlaps
  the board.
- **Background** (Jobs tab options under the drill map), plotted by kicad-cli with
  `--drill-shape-opt 0` (KiCad would otherwise draw filled drill marks under the symbols):
  - *Show the board outline* (default): Edge.Cuts;
  - *Add the drawing sheet*: frame and title block (`--include-border-title`); the table
    then starts at 20 mm to stay inside the frame. Alone, it is plotted from a `User.N`
    layer absent from the board, which gives the drawing sheet only;
  - neither: only the page size is kept, the symbols stay at the same coordinates.

## BOM fields discovery (plugin side)

![bom-fields](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/bom-fields.puml)

<sub>Source: [diagrams/bom-fields.puml](diagrams/bom-fields.puml)</sub>

The table order is the CSV column order; ticked rows become `fields_ordered` /
`fields_labels` of the native `sch_export_bom` job, "Group" rows become `fields_group_by`.
