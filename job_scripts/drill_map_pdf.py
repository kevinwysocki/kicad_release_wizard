import argparse
import math
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except Exception as e:
    print(f"[ERROR] Cannot import fitz / PyMuPDF: {e}", file=sys.stderr, flush=True)
    sys.exit(2)

PAPER_SIZES_MM = {
    'A0': (1189.0, 841.0), 'A1': (841.0, 594.0), 'A2': (594.0, 420.0),
    'A3': (420.0, 297.0), 'A4': (297.0, 210.0), 'A5': (210.0, 148.0),
    'A': (279.4, 215.9), 'B': (431.8, 279.4), 'C': (558.8, 431.8),
    'D': (863.6, 558.8), 'E': (1117.6, 863.6),
    'USLetter': (279.4, 215.9), 'USLegal': (355.6, 215.9), 'USLedger': (431.8, 279.4),
}

def tokenize(text):
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c in '()':
            yield c
            i += 1
            continue
        if c == '"':
            i += 1
            buf = []
            while i < n:
                if text[i] == '\\' and i + 1 < n:
                    buf.append(text[i + 1])
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                buf.append(text[i])
                i += 1
            yield ''.join(buf)
            continue
        j = i
        while j < n and not text[j].isspace() and text[j] not in '()':
            j += 1
        yield text[i:j]
        i = j

def parse_sexpr(tokens):
    stack = [[]]
    for tok in tokens:
        if tok == '(':
            new = []
            stack[-1].append(new)
            stack.append(new)
        elif tok == ')':
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1].append(tok)
    return stack[0]

def as_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def children(node, name=None):
    if not isinstance(node, list):
        return []
    out = []
    for c in node:
        if isinstance(c, list) and c:
            if name is None or c[0] == name:
                out.append(c)
    return out

def first_child(node, name):
    cs = children(node, name)
    return cs[0] if cs else None

def walk(node):
    if isinstance(node, list):
        yield node
        for x in node:
            yield from walk(x)

def get_board_node(root):
    if isinstance(root, list):
        for node in root:
            if isinstance(node, list) and node and node[0] == 'kicad_pcb':
                return node
    return root

def get_paper_size_mm(root):
    board = get_board_node(root)
    paper = first_child(board, 'paper')
    if not paper or len(paper) < 2:
        return None
    if len(paper) >= 4:
        w = as_float(paper[2], None)
        h = as_float(paper[3], None)
        if w and h and w > 0 and h > 0:
            name = str(paper[1]).strip().strip('"') or 'custom'
            return (float(w), float(h), name)
    if len(paper) >= 3:
        w = as_float(paper[1], None)
        h = as_float(paper[2], None)
        if w and h and w > 0 and h > 0:
            return (float(w), float(h), 'custom')
    name = str(paper[1]).strip().strip('"')
    key = name.replace(' ', '')
    size = PAPER_SIZES_MM.get(key) or PAPER_SIZES_MM.get(key.upper())
    if not size:
        return None
    w, h = size
    tail = ' '.join(str(x).lower() for x in paper[2:])
    if 'portrait' in tail and w > h:
        w, h = h, w
    elif 'landscape' in tail and h > w:
        w, h = h, w
    return (w, h, key)

def transform_point(fx, fy, fr_deg, px, py):
    a = math.radians(fr_deg)
    ca = math.cos(a)
    sa = math.sin(a)
    return (fx + ca * px - sa * py, fy + sa * px + ca * py)

def get_layer(node):
    lay = first_child(node, 'layer')
    if lay and len(lay) >= 2:
        return str(lay[1])
    return ''

def get_point(node, name):
    p = first_child(node, name)
    if p and len(p) >= 3:
        return (as_float(p[1]), as_float(p[2]))
    return None

def get_stroke_width(node, default=0.05):
    st = first_child(node, 'stroke')
    if st:
        w = first_child(st, 'width')
        if w and len(w) >= 2:
            return max(0.0001, as_float(w[1], default))
    w = first_child(node, 'width')
    if w and len(w) >= 2:
        return max(0.0001, as_float(w[1], default))
    return default

def is_solid_fill(node):
    f = first_child(node, 'fill')
    if not f:
        return False
    vals = [str(x).lower() for x in f if not isinstance(x, list)]
    if 'solid' in vals or 'yes' in vals:
        return True
    t = first_child(f, 'type')
    if t and len(t) >= 2 and str(t[1]).lower() in ('solid', 'yes'):
        return True
    return False

def node_has_layer(node, target='F.Cu'):
    layers = first_child(node, 'layers')
    if layers:
        for item in layers[1:]:
            if isinstance(item, str) and item.strip().strip('"') == target:
                return True
    lay = first_child(node, 'layer')
    if lay and len(lay) >= 2 and str(lay[1]).strip().strip('"') == target:
        return True
    return False

def get_size_xy(node):
    sz = first_child(node, 'size')
    if sz and len(sz) >= 3:
        return (as_float(sz[1]), as_float(sz[2]))
    return None

def drill_from_pad(pad):
    d = first_child(pad, 'drill')
    if not d or len(d) < 2:
        return None
    if len(d) >= 4 and str(d[1]).lower() == 'oval':
        return (as_float(d[2]), as_float(d[3]))
    return (as_float(d[1]), as_float(d[1]))

def collect_drills(root):
    drills = []
    for node in walk(root):
        if not node:
            continue
        if node[0] == 'via':
            at = first_child(node, 'at')
            dr = first_child(node, 'drill')
            if at and len(at) >= 3 and dr and len(dr) >= 2:
                drills.append((as_float(at[1]), as_float(at[2]), as_float(dr[1]), as_float(dr[1])))
        elif node[0] == 'footprint':
            fat = first_child(node, 'at')
            fx = as_float(fat[1]) if fat and len(fat) >= 3 else 0.0
            fy = as_float(fat[2]) if fat and len(fat) >= 3 else 0.0
            fr = as_float(fat[3]) if fat and len(fat) >= 4 else 0.0
            for pad in children(node, 'pad'):
                d = drill_from_pad(pad)
                if not d:
                    continue
                pat = first_child(pad, 'at')
                px = as_float(pat[1]) if pat and len(pat) >= 3 else 0.0
                py = as_float(pat[2]) if pat and len(pat) >= 3 else 0.0
                x, y = transform_point(fx, fy, fr, px, py)
                drills.append((x, y, d[0], d[1]))
    return drills

def arc_points_from_3pts(p1, p2, p3, n=32):
    x1, y1 = p1; x2, y2 = p2; x3, y3 = p3
    d = 2 * (x1*(y2-y3) + x2*(y3-y1) + x3*(y1-y2))
    if abs(d) < 1e-9:
        return [p1, p2, p3]
    ux = ((x1*x1+y1*y1)*(y2-y3) + (x2*x2+y2*y2)*(y3-y1) + (x3*x3+y3*y3)*(y1-y2)) / d
    uy = ((x1*x1+y1*y1)*(x3-x2) + (x2*x2+y2*y2)*(x1-x3) + (x3*x3+y3*y3)*(x2-x1)) / d
    r = math.hypot(x1-ux, y1-uy)
    a1 = math.atan2(y1-uy, x1-ux)
    a2 = math.atan2(y2-uy, x2-ux)
    a3 = math.atan2(y3-uy, x3-ux)
    def norm(a):
        while a < 0: a += 2*math.pi
        while a >= 2*math.pi: a -= 2*math.pi
        return a
    na1, na2, na3 = norm(a1), norm(a2), norm(a3)
    ccw_span = (na3 - na1) % (2*math.pi)
    mid_on_ccw = ((na2 - na1) % (2*math.pi)) <= ccw_span
    total = ccw_span if mid_on_ccw else ccw_span - 2*math.pi
    steps = max(4, n)
    return [(ux + r * math.cos(a1 + total * i / steps), uy + r * math.sin(a1 + total * i / steps)) for i in range(steps + 1)]

def collect_fcu_graphics(root):
    """Collect only 4.0 mm round F.Cu camera fiducials.

    The drill-map overlay must not bring arbitrary F.Cu graphics. We keep:
      - solid filled board-level gr_circle on F.Cu, diameter 4.0 mm,
      - solid filled footprint-level fp_circle on F.Cu, diameter 4.0 mm,
      - circular pads present on F.Cu, size 4.0 x 4.0 mm.

    This covers the common KiCad cases where camera fiducials / mires are made
    as SMD circular pads rather than graphic circles.
    """
    board = get_board_node(root)
    out = []
    target_diam_mm = 4.0
    tol_mm = 0.08
    candidates = 0
    kept = 0
    kept_graphic = 0
    kept_pad = 0

    def near_4mm(dia):
        return dia is not None and abs(float(dia) - target_diam_mm) <= tol_mm

    def circle_diameter(center, end):
        return 2.0 * math.hypot(end[0] - center[0], end[1] - center[1])

    def add_circle_if_camera_mark(center, end, width=0.001, fill=True, source='circle'):
        nonlocal candidates, kept, kept_graphic
        candidates += 1
        dia = circle_diameter(center, end)
        if not near_4mm(dia):
            return
        if not fill:
            return
        out.append({
            'kind': 'circle',
            'center': center,
            'end': end,
            'width': max(0.0001, width),
            'fill': True,
            'diameter_mm': dia,
            'source': source,
        })
        kept += 1
        kept_graphic += 1

    def add_pad_if_camera_mark(center, diameter, source='pad'):
        nonlocal candidates, kept, kept_pad
        candidates += 1
        if not near_4mm(diameter):
            return
        r = float(diameter) / 2.0
        out.append({
            'kind': 'circle',
            'center': center,
            'end': (center[0] + r, center[1]),
            'width': 0.001,
            'fill': True,
            'diameter_mm': float(diameter),
            'source': source,
        })
        kept += 1
        kept_pad += 1

    # Board-level graphic filled circles.
    for node in children(board):
        if not node or not isinstance(node[0], str):
            continue
        if node[0] != 'gr_circle' or get_layer(node) != 'F.Cu':
            continue
        c = get_point(node, 'center')
        e = get_point(node, 'end')
        if not (c and e):
            continue
        add_circle_if_camera_mark(c, e, width=get_stroke_width(node, 0.001), fill=is_solid_fill(node), source='gr_circle')

    for fp in children(board, 'footprint'):
        fat = first_child(fp, 'at')
        fx = as_float(fat[1]) if fat and len(fat) >= 3 else 0.0
        fy = as_float(fat[2]) if fat and len(fat) >= 3 else 0.0
        fr = as_float(fat[3]) if fat and len(fat) >= 4 else 0.0
        def tr(p): return transform_point(fx, fy, fr, p[0], p[1])

        # Footprint graphic filled circles.
        for node in children(fp, 'fp_circle'):
            if get_layer(node) != 'F.Cu':
                continue
            c = get_point(node, 'center')
            e = get_point(node, 'end')
            if not (c and e):
                continue
            add_circle_if_camera_mark(tr(c), tr(e), width=get_stroke_width(node, 0.001), fill=is_solid_fill(node), source='fp_circle')

        # Circular F.Cu pads, common for fiducials / mires camera.
        for pad in children(fp, 'pad'):
            if not node_has_layer(pad, 'F.Cu'):
                continue
            shape = str(pad[2]).lower() if len(pad) >= 3 else ''
            size = get_size_xy(pad)
            if not size:
                continue
            sx, sy = size
            if sx <= 0 or sy <= 0:
                continue
            # KiCad uses shape "circle" for true round pads; accept oval only
            # when X and Y are effectively identical.
            if shape not in ('circle', 'oval'):
                continue
            if abs(sx - sy) > tol_mm:
                continue
            pat = first_child(pad, 'at')
            px = as_float(pat[1]) if pat and len(pat) >= 3 else 0.0
            py = as_float(pat[2]) if pat and len(pat) >= 3 else 0.0
            x, y = tr((px, py))
            add_pad_if_camera_mark((x, y), (sx + sy) / 2.0, source='pad')

    print(f'[INFO] F.Cu round fiducial candidates={candidates}', flush=True)
    print(f'[INFO] F.Cu 4.0mm fiducials kept={kept} (graphics={kept_graphic}, pads={kept_pad}, tolerance +/- {tol_mm:.3f} mm)', flush=True)
    return out

def write_pdf(drills, graphics, output, paper_size=None):
    if not drills:
        raise RuntimeError('No drilled pads / vias found')

    scale = 72.0 / 25.4

    if paper_size:
        paper_w_mm, paper_h_mm, paper_name = paper_size
        minx = 0.0
        miny = 0.0
        page_w = paper_w_mm * scale
        page_h = paper_h_mm * scale
        print(f'[INFO] Paper={paper_name} {paper_w_mm:.3f}x{paper_h_mm:.3f} mm', flush=True)
        print('[INFO] Coordinate mode=absolute KiCad sheet coordinates, no bbox crop, no XY offset', flush=True)
    else:
        xs = [d[0] for d in drills]
        ys = [d[1] for d in drills]
        margin = 10.0
        minx, maxx = min(xs) - margin, max(xs) + margin
        miny, maxy = min(ys) - margin, max(ys) + margin
        page_w = (maxx - minx) * scale
        page_h = (maxy - miny) * scale
        print('[WARN] No KiCad paper definition found: using drill bbox fallback, positions may be offset', flush=True)

    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)

    def pt(x, y):
        return fitz.Point((x - minx) * scale, (y - miny) * scale)

    def draw_one(g):
        kind = g.get('kind')

        if kind == 'circle' and g.get('center') and g.get('end'):
            c = g['center']
            e = g['end']

            r_mm = math.hypot(e[0] - c[0], e[1] - c[1])
            r_pt = r_mm * scale
            cp = pt(*c)

            width_mm = max(0.0001, float(g.get('width') or 0.001))
            width_pt = width_mm * scale

            page.draw_circle(
                cp,
                r_pt,
                color=(0, 0, 0),
                fill=(0, 0, 0) if g.get('fill') else None,
                width=width_pt,
            )
            return True

        return False

    graphics_drawn = 0
    for g in graphics:
        try:
            if draw_one(g):
                graphics_drawn += 1
        except Exception as e:
            print(f'[WARN] F.Cu graphic skipped: {e}', flush=True)

    valid = 0
    marker_length_mm = 0.1
    marker_width_mm = 0.01
    half_len_pt = (marker_length_mm / 2.0) * scale
    marker_width_pt = marker_width_mm * scale

    for x, y, dx, dy in drills:
        if dx <= 0 or dy <= 0:
            continue

        c = pt(x, y)

        # Marque de perçage demandée :
        # - position = centre du perçage
        # - trait vertical
        # - longueur = 0.1 mm
        # - épaisseur = 0.01 mm
        page.draw_line(
            fitz.Point(c.x, c.y - half_len_pt),
            fitz.Point(c.x, c.y + half_len_pt),
            color=(0, 0, 0),
            width=marker_width_pt,
        )

        valid += 1

    print(f'[INFO] F.Cu 4.0mm camera fiducials drawn={graphics_drawn}', flush=True)
    print(f'[INFO] Drill vertical marks drawn={valid}', flush=True)
    print(f'[INFO] Drill marker geometry: vertical line, length={marker_length_mm:.3f} mm, stroke={marker_width_mm:.3f} mm', flush=True)
    print('[INFO] Drill positions are read from pad/via drill centers; circles are not drawn for drill holes', flush=True)

    doc.save(str(output), garbage=3, deflate=True)
    doc.close()

def main():
    ap = argparse.ArgumentParser(description='Generate vector drill-map PDF: drill circles + F.Cu 4mm camera fiducials from circles or pads, exact drill diameters, sheet size.')
    ap.add_argument('--pcb', required=True); ap.add_argument('--output', required=True)
    args = ap.parse_args(); pcb = Path(args.pcb); output = Path(args.output)
    if not pcb.exists(): raise FileNotFoundError(pcb)
    text = pcb.read_text(encoding='utf-8', errors='ignore')
    root = parse_sexpr(tokenize(text))
    drills = collect_drills(root); graphics = collect_fcu_graphics(root); paper_size = get_paper_size_mm(root)
    print(f'[INFO] Drill positions={len(drills)}', flush=True)
    print(f'[INFO] F.Cu 4.0mm camera fiducials collected={len(graphics)}', flush=True)
    print('[INFO] F.Cu overlay filter: only 4.0 mm round fiducials are added: solid filled gr_circle/fp_circle and circular F.Cu pads; all other F.Cu objects are ignored.', flush=True)
    write_pdf(drills, graphics, output, paper_size=paper_size)
    print(f'[OK] Written {output}', flush=True)
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f'[ERROR] {e}', file=sys.stderr, flush=True)
        sys.exit(1)
