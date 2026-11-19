"""Drill map PDF: one symbol per drill diameter and a drill table (top left).

Inputs are produced by kicad-cli, so the map matches the fabrication files exactly:
- the Excellon drill files (PTH and NPTH, mm, decimal, absolute origin, G85 slots),
- a background PDF plotted by kicad-cli with the board's page settings: it provides the
  page size and, optionally, the board outline and / or the drawing sheet, in the same
  coordinates as the board (1 mm = 72/25.4 pt).

    python drill_map_pdf.py --base edge.pdf --drill board-PTH.drl board-NPTH.drl --output map.pdf
"""

import argparse
import math
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

PT_PER_MM = 72.0 / 25.4
BLACK = (0, 0, 0)

# ------------------------------------------------------------------- Excellon

_TOOL_DEF_RE = re.compile(r"^T(\d+)C([\d.]+)")
_TOOL_SEL_RE = re.compile(r"^T(\d+)$")
_HIT_RE = re.compile(r"^X(-?[\d.]+)Y(-?[\d.]+)(?:G85X(-?[\d.]+)Y(-?[\d.]+))?$")
_FUNCTION_RE = re.compile(r"TA\.AperFunction,([^,]+),([^,]+),(\w+)")


def parse_excellon(path):
    """Tools of a KiCad Excellon file (mm, decimal, absolute): list of dicts with
    diameter, plated, function, hits [(x, y)] and slots [((x1, y1), (x2, y2))].
    Y is negated back to board coordinates (Excellon Y points up)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    plated = "NonPlated" not in text and not Path(path).stem.upper().endswith("NPTH")
    tools = {}
    current = None
    pending_function = ""
    for raw in text.splitlines():
        line = raw.strip()
        m = _FUNCTION_RE.search(line)
        if m:
            pending_function = m.group(3)
            continue
        m = _TOOL_DEF_RE.match(line)
        if m:
            tools[m.group(1)] = {
                "diameter": float(m.group(2)),
                "plated": plated,
                "function": pending_function,
                "hits": [],
                "slots": [],
            }
            pending_function = ""
            continue
        m = _TOOL_SEL_RE.match(line)
        if m:
            current = tools.get(m.group(1))
            continue
        m = _HIT_RE.match(line)
        if m and current is not None:
            x1, y1 = float(m.group(1)), -float(m.group(2))
            if m.group(3) is not None:
                current["slots"].append(((x1, y1), (float(m.group(3)), -float(m.group(4)))))
            else:
                current["hits"].append((x1, y1))
    return [t for t in tools.values() if t["hits"] or t["slots"]]


def drill_groups(drill_files):
    """One group per (plated, diameter, hole/slot), sorted: plated first, then by diameter."""
    groups = {}
    for path in drill_files:
        for tool in parse_excellon(path):
            for kind, items in (("hole", tool["hits"]), ("slot", tool["slots"])):
                if not items:
                    continue
                key = (not tool["plated"], round(tool["diameter"], 4), kind)
                g = groups.setdefault(key, {
                    "diameter": tool["diameter"], "plated": tool["plated"], "kind": kind,
                    "functions": set(), "items": [],
                })
                g["items"].extend(items)
                if tool["function"]:
                    g["functions"].add(tool["function"])
    return [groups[k] for k in sorted(groups)]


def group_label(g):
    label = "PTH" if g["plated"] else "NPTH"
    if g["kind"] == "slot":
        label += " slot"
    elif g["functions"] == {"ViaDrill"}:
        label += " via"
    return label


# -------------------------------------------------------------------- symbols

OUTLINES = [None, "circle", "square", "triangle", "diamond", "hexagon", "triangle_down"]
# Simple symbols first: +, x, circle, square, triangle, ... then combinations.
SYMBOLS = [(None, "plus"), (None, "cross")] + [(o, None) for o in OUTLINES[1:]] + [
    (o, m) for m in ("plus", "cross") for o in OUTLINES[1:]
]


def _polygon(cx, cy, r, sides, start_deg):
    return [
        fitz.Point(cx + r * math.cos(math.radians(start_deg + i * 360 / sides)),
                   cy + r * math.sin(math.radians(start_deg + i * 360 / sides)))
        for i in range(sides)
    ]


def draw_symbol(page, center, size_pt, index, width_pt):
    """Draw symbol number <index> centred on <center>, fitting a size_pt square."""
    outline, mark = SYMBOLS[index % len(SYMBOLS)]
    cx, cy = center.x, center.y
    r = size_pt / 2
    shape = page.new_shape()
    if outline == "circle":
        shape.draw_circle(center, r)
    elif outline == "square":
        shape.draw_rect(fitz.Rect(cx - r, cy - r, cx + r, cy + r))
    elif outline == "triangle":
        shape.draw_polyline(_polygon(cx, cy, r, 3, -90) + [_polygon(cx, cy, r, 3, -90)[0]])
    elif outline == "triangle_down":
        shape.draw_polyline(_polygon(cx, cy, r, 3, 90) + [_polygon(cx, cy, r, 3, 90)[0]])
    elif outline == "diamond":
        shape.draw_polyline(_polygon(cx, cy, r, 4, -90) + [_polygon(cx, cy, r, 4, -90)[0]])
    elif outline == "hexagon":
        shape.draw_polyline(_polygon(cx, cy, r, 6, 0) + [_polygon(cx, cy, r, 6, 0)[0]])
    inner = r if outline is None else r * 0.7
    if mark == "plus":
        shape.draw_line(fitz.Point(cx - inner, cy), fitz.Point(cx + inner, cy))
        shape.draw_line(fitz.Point(cx, cy - inner), fitz.Point(cx, cy + inner))
    elif mark == "cross":
        d = inner * 0.7071
        shape.draw_line(fitz.Point(cx - d, cy - d), fitz.Point(cx + d, cy + d))
        shape.draw_line(fitz.Point(cx - d, cy + d), fitz.Point(cx + d, cy - d))
    shape.finish(color=BLACK, fill=None, width=width_pt, closePath=False)
    shape.commit()


def symbol_size_mm(diameter):
    """Symbol size on the board: the hole diameter, kept readable (0.6 to 2.5 mm)."""
    return min(2.5, max(0.6, diameter))


# ---------------------------------------------------------------------- table

def draw_table(page, groups, origin_mm=(10.0, 10.0)):
    """Drill table at the top left of the page; returns its rectangle (pt)."""
    cols = [("Symbol", 14), ("Ø (mm)", 18), ("Count", 14), ("Type", 22)]  # widths in mm
    row_h = 5.0 * PT_PER_MM
    x0, y0 = origin_mm[0] * PT_PER_MM, origin_mm[1] * PT_PER_MM
    widths = [w * PT_PER_MM for _, w in cols]
    total_w = sum(widths)
    font = 7.5
    line = 0.25

    def cell_text(col, row, text, bold=False):
        x = x0 + sum(widths[:col])
        y = y0 + (row + 1) * row_h  # row 0 is the title
        width = fitz.get_text_length(text, fontname="hebo" if bold else "helv", fontsize=font)
        page.insert_text(
            fitz.Point(x + (widths[col] - width) / 2, y + row_h / 2 + font * 0.35),
            text, fontsize=font, fontname="hebo" if bold else "helv", color=BLACK,
        )

    title = "Drill table"
    page.insert_text(fitz.Point(x0, y0 + row_h * 0.7), title, fontsize=font + 1.5, fontname="hebo", color=BLACK)

    for c, (name, _w) in enumerate(cols):
        cell_text(c, 0, name, bold=True)
    total = 0
    for i, g in enumerate(groups):
        row = i + 1
        count = len(g["items"])
        total += count
        cy = y0 + (row + 1) * row_h + row_h / 2
        draw_symbol(page, fitz.Point(x0 + widths[0] / 2, cy), 3.0 * PT_PER_MM, i, line)
        cell_text(1, row, f"{g['diameter']:.3f}")
        cell_text(2, row, str(count))
        cell_text(3, row, group_label(g))
    last = len(groups) + 1
    cell_text(0, last, "Total", bold=True)
    cell_text(2, last, str(total), bold=True)

    rows = len(groups) + 2  # header + groups + total
    top = y0 + row_h
    shape = page.new_shape()
    for r in range(rows + 1):
        y = top + r * row_h
        shape.draw_line(fitz.Point(x0, y), fitz.Point(x0 + total_w, y))
    x = x0
    for w in [0] + widths:
        x += w
        shape.draw_line(fitz.Point(x, top), fitz.Point(x, top + rows * row_h))
    shape.finish(color=BLACK, width=line)
    shape.commit()
    return fitz.Rect(x0, y0, x0 + total_w, top + rows * row_h)


# ------------------------------------------------------------------------ map

def draw_drill_map(base_pdf, drill_files, output, background=True, table_origin_mm=(10.0, 10.0), log=print):
    groups = drill_groups(drill_files)
    if not groups:
        raise RuntimeError("No drill hits found in the Excellon files")
    if len(groups) > len(SYMBOLS):
        log(f"WARN {len(groups)} drill sizes for {len(SYMBOLS)} symbols: symbols are reused")

    doc = fitz.open(str(base_pdf))
    if not background:
        # Same page size (board coordinates stay valid), without the background drawing.
        rect = doc[0].rect
        doc.close()
        doc = fitz.open()
        doc.new_page(width=rect.width, height=rect.height)
    page = doc[0]
    holes_rect = fitz.Rect()
    for i, g in enumerate(groups):
        size_pt = symbol_size_mm(g["diameter"]) * PT_PER_MM
        width_pt = max(0.05, symbol_size_mm(g["diameter"]) * 0.08) * PT_PER_MM
        for item in g["items"]:
            if g["kind"] == "slot":
                (x1, y1), (x2, y2) = item
                p1, p2 = fitz.Point(x1 * PT_PER_MM, y1 * PT_PER_MM), fitz.Point(x2 * PT_PER_MM, y2 * PT_PER_MM)
                # Slot outline: a line as wide as the slot, drawn as a thin stadium.
                shape = page.new_shape()
                shape.draw_line(p1, p2)
                shape.finish(color=(0.6, 0.6, 0.6), width=g["diameter"] * PT_PER_MM, lineCap=1)
                shape.commit()
                center = fitz.Point((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
            else:
                center = fitz.Point(item[0] * PT_PER_MM, item[1] * PT_PER_MM)
            draw_symbol(page, center, size_pt, i, width_pt)
            r = size_pt / 2
            box = fitz.Rect(center.x - r, center.y - r, center.x + r, center.y + r)
            holes_rect = box if holes_rect.is_empty else holes_rect | box

    table = draw_table(page, groups, table_origin_mm)
    if table.intersects(holes_rect):
        log("WARN the drill table overlaps the board: move the board on its page in KiCad")

    for i, g in enumerate(groups):
        outline, mark = SYMBOLS[i % len(SYMBOLS)]
        log(f"{group_label(g):9s} Ø{g['diameter']:.3f} mm x{len(g['items']):<5d} symbol={outline or ''}{'+' if mark == 'plus' else 'x' if mark == 'cross' else ''}")
    log(f"Drill sizes={len(groups)} holes={sum(len(g['items']) for g in groups)}")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output), garbage=3, deflate=True)
    doc.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="background PDF plotted by kicad-cli (page size, outline, sheet)")
    ap.add_argument("--drill", required=True, nargs="+", help="Excellon files (mm, decimal, absolute)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--no-background", action="store_true", help="blank page of the base PDF's size")
    args = ap.parse_args()
    draw_drill_map(args.base, args.drill, args.output, background=not args.no_background)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        sys.exit(1)
