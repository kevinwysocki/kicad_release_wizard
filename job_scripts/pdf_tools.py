"""PDF post-processing for the per-layer PDFs (requires PyMuPDF).

- invert_pdf: black/white inversion inside the real board outline (pcbnew polygons,
  internal cut-outs included), with an optional overlay drawn on top unchanged.
- rotate_pdf_180: 180 degree rotation baked into the page content.

Usable as a module (from release_jobs.py) or from the command line.
"""

import argparse
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

PT_PER_MM = 72.0 / 25.4


# --------------------------------------------------------------------- inversion

def _point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            x_int = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_int:
                inside = not inside
        j = i
    return inside


class BoardRegion:
    """Board area: union of outlines, each outline minus its holes (PDF points, y down)."""

    def __init__(self, polygons):
        self.polygons = polygons
        xs = [p[0] for poly in polygons for p in poly["outer"]]
        ys = [p[1] for poly in polygons for p in poly["outer"]]
        self.bbox = fitz.Rect(min(xs), min(ys), max(xs), max(ys))

    @classmethod
    def from_json(cls, outline_json, page_width, mirror):
        """Board coordinates (mm) map 1:1 to the plotted page; mirror flips around the page width."""
        data = json.loads(Path(outline_json).read_text(encoding="utf-8"))

        def tr(pt):
            x = pt[0] * PT_PER_MM
            y = pt[1] * PT_PER_MM
            return (page_width - x, y) if mirror else (x, y)

        polygons = []
        for ol in data.get("outlines", []):
            outer = [tr(p) for p in ol.get("outer", [])]
            holes = [[tr(p) for p in h] for h in ol.get("holes", []) if len(h) >= 3]
            if len(outer) >= 3:
                polygons.append({"outer": outer, "holes": holes})
        if not polygons:
            raise RuntimeError(f"No board outline in {outline_json}")
        return cls(polygons)

    def contains(self, x, y):
        for poly in self.polygons:
            if _point_in_ring(x, y, poly["outer"]) and not any(
                _point_in_ring(x, y, h) for h in poly["holes"]
            ):
                return True
        return False

    def touches_rect(self, r):
        """True when the rectangle overlaps the board area (sampled)."""
        if not r.intersects(self.bbox):
            return False
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        samples = [
            (cx, cy), (r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1),
            (cx, r.y0), (cx, r.y1), (r.x0, cy), (r.x1, cy),
        ]
        if any(self.contains(x, y) for x, y in samples):
            return True
        # Thin items crossing a notch / cut-out edge: any board vertex inside the item box.
        for poly in self.polygons:
            for ring in [poly["outer"]] + poly["holes"]:
                for x, y in ring:
                    if r.x0 <= x <= r.x1 and r.y0 <= y <= r.y1:
                        return True
        return False


def _is_black(rgb):
    return rgb is not None and all(v < 0.12 for v in rgb[:3])


def _copy_path(shape, items):
    for it in items:
        op = it[0]
        if op == "l":
            shape.draw_line(it[1], it[2])
        elif op == "c":
            shape.draw_bezier(it[1], it[2], it[3], it[4])
        elif op == "re":
            shape.draw_rect(it[1])
        elif op == "qu":
            shape.draw_quad(it[1])


def _fill_board_black(page, region):
    # Outer contour and cut-outs in one even-odd path per outline: cut-outs stay white.
    shape = page.new_shape()
    for poly in region.polygons:
        shape.draw_polyline(poly["outer"] + [poly["outer"][0]])
        for hole in poly["holes"]:
            shape.draw_polyline(hole + [hole[0]])
        shape.finish(color=None, fill=(0, 0, 0), even_odd=True, closePath=True)
    shape.commit(overlay=True)


def _repaint_white(page, region, drawings):
    # Repaint in white the original black artwork touching the board. Whatever lies
    # outside the board is white paper anyway, so repainting a whole item that
    # straddles the edge (e.g. castellated pad openings) is exact.
    shape = page.new_shape()
    count = 0
    for d in drawings:
        black_fill = _is_black(d.get("fill"))
        black_stroke = _is_black(d.get("color"))
        if not (black_fill or black_stroke):
            continue
        r = fitz.Rect(d.get("rect"))
        width = float(d.get("width") or 0)
        if black_stroke and width:
            r = fitz.Rect(r.x0 - width / 2, r.y0 - width / 2, r.x1 + width / 2, r.y1 + width / 2)
        if not region.touches_rect(r):
            continue
        _copy_path(shape, d.get("items", []))
        cap = d.get("lineCap")
        if isinstance(cap, (list, tuple)):
            cap = cap[0] if cap else 0
        shape.finish(
            color=(1, 1, 1) if black_stroke else None,
            fill=(1, 1, 1) if black_fill else None,
            width=width or 0.1,
            lineCap=int(cap or 0),
            lineJoin=int(d.get("lineJoin") or 0),
            even_odd=bool(d.get("even_odd", False)),
            closePath=bool(d.get("closePath", False)),
        )
        count += 1
    shape.commit(overlay=True)
    return count


def invert_pdf(mask_pdf, outline_json, output_pdf, mirror=False, overlay_pdf=None, log=print):
    """Invert black/white inside the board outline of a one-page black & white layer PDF."""
    mask = fitz.open(str(mask_pdf))
    if len(mask) != 1:
        raise RuntimeError("Expected a one-page layer PDF")
    out = fitz.open()
    out.insert_pdf(mask, from_page=0, to_page=0)
    mask.close()
    page = out[0]

    region = BoardRegion.from_json(outline_json, page.rect.width, mirror)
    b = region.bbox
    log(
        f"Inversion: outlines={len(region.polygons)} "
        f"cut-outs={sum(len(p['holes']) for p in region.polygons)} mirror={mirror} "
        f"board=({b.x0 / PT_PER_MM:.2f},{b.y0 / PT_PER_MM:.2f})-({b.x1 / PT_PER_MM:.2f},{b.y1 / PT_PER_MM:.2f}) mm"
    )
    if not page.rect.contains(b):
        raise RuntimeError("Board outline lies outside the PDF page: plot placement does not match board coordinates")

    original = page.get_drawings()  # snapshot BEFORE the black fill
    _fill_board_black(page, region)
    log(f"Inversion: {_repaint_white(page, region, original)} drawings repainted white")

    if overlay_pdf:
        ov = fitz.open(str(overlay_pdf))
        page.show_pdf_page(page.rect, ov, 0, overlay=True)
        ov.close()

    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    if output_pdf.exists():
        output_pdf.unlink()
    out.save(str(output_pdf), garbage=4, deflate=True)
    out.close()


# ---------------------------------------------------------------------- rotation

def rotate_pdf_180(input_pdf, output_pdf):
    """180 degree rotation baked into the page content (not page-rotation metadata),
    so editors / RIPs that ignore /Rotate still see the rotated geometry."""
    src = fitz.open(str(input_pdf))
    out = fitz.open()
    try:
        for number, page in enumerate(src):
            dst = out.new_page(width=page.rect.width, height=page.rect.height)
            dst.show_pdf_page(dst.rect, src, number, rotate=180)
        out.save(str(output_pdf), garbage=3, deflate=True)
    finally:
        out.close()
        src.close()


# ---------------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="PDF post-processing for Kicad Release Wizard")
    sub = ap.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("invert")
    inv.add_argument("--mask", required=True)
    inv.add_argument("--outline", required=True)
    inv.add_argument("--output", required=True)
    inv.add_argument("--mirror", action="store_true")
    inv.add_argument("--overlay", default=None)
    rot = sub.add_parser("rotate")
    rot.add_argument("--input", required=True)
    rot.add_argument("--output", required=True)
    args = ap.parse_args()
    if args.cmd == "invert":
        invert_pdf(args.mask, args.outline, args.output, args.mirror, args.overlay)
    else:
        rotate_pdf_180(args.input, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        sys.exit(1)
