"""Extract the exact board outline (with internal cut-outs) through pcbnew.

The result is written as JSON next to the helper scripts and used by
invert_mask_inside_contours.py, so the PDF inversion follows the real board
shape instead of re-deriving it from a plotted Edge.Cuts PDF.

JSON format (coordinates in mm, KiCad board coordinates, Y pointing down):
    {"units": "mm", "outlines": [{"outer": [[x, y], ...], "holes": [[[x, y], ...], ...]}]}
"""

import json

import pcbnew

NM_PER_MM = 1_000_000.0


def _chain_points(chain):
    pts = []
    for i in range(chain.PointCount()):
        p = chain.CPoint(i)
        pts.append([p.x / NM_PER_MM, p.y / NM_PER_MM])
    return pts


def board_outline_polygons(board):
    """Return [{'outer': [...], 'holes': [[...], ...]}] for the board, in mm."""
    polyset = pcbnew.SHAPE_POLY_SET()
    # (outlines, aInferOutlineIfNecessary, ...): no inferred outline, Edge.Cuts only.
    ok = board.GetBoardPolygonOutlines(polyset, False)
    if not ok:
        raise RuntimeError("Board outline (Edge.Cuts) is not a valid closed shape")

    outlines = []
    for i in range(polyset.OutlineCount()):
        outer = _chain_points(polyset.Outline(i))
        holes = [_chain_points(polyset.Hole(i, h)) for h in range(polyset.HoleCount(i))]
        if len(outer) >= 3:
            outlines.append({"outer": outer, "holes": [h for h in holes if len(h) >= 3]})
    if not outlines:
        raise RuntimeError("No board outline found on Edge.Cuts")
    return outlines


def write_board_outline(pcb_path, json_path):
    """Load the saved board file (what kicad-cli will plot) and write its outline."""
    try:
        import wx

        no_log = wx.LogNull()  # loading may log font substitution warnings
    except Exception:
        no_log = None
    try:
        board = pcbnew.LoadBoard(str(pcb_path))
    except Exception:
        board = pcbnew.GetBoard()
    finally:
        del no_log
    data = {"units": "mm", "outlines": board_outline_polygons(board)}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data
