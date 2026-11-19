import json
import os
import re
import subprocess
import shutil
import sys
import threading
from pathlib import Path

import pcbnew
import wx
import wx.grid as wxgrid

from .board_outline import write_board_outline
from .bom_fields import default_bom_fields, merge_bom_fields
from .i18n import tr
from .platform_tools import NO_WINDOW, command_path, find_kicad_cli, find_python


PLUGIN_DIR = Path(__file__).resolve().parent
JOB_SCRIPTS_DIR = PLUGIN_DIR / "job_scripts"

PROFILE_VERSION = 1

# (job id, enabled by default). Labels and tooltips come from i18n: job_<id>, job_<id>_tip.
DEFAULT_JOBS = [
    ("erc", True),
    ("drc", True),
    ("sch_pdf", True),
    ("pcb_pdf", True),
    ("pcb_implantation", True),
    ("drill_map_pdf", True),
    ("bom_csv", True),
    ("pnp_csv", True),
    ("pcb_drill", True),
    ("zip_gerber", True),
    ("meca_step", True),
]

# Per-layer export formats (Layers tab) and their default state.
LAYER_FORMATS = (("gerber", True), ("pdf", True), ("svg", False), ("dxf", False))
# Per-layer formats produced by the "layers" job script (Gerbers are a native job).
SCRIPTED_LAYER_FORMATS = ("pdf", "svg", "dxf")

# Layers ticked for export by default (standard fabrication set) - inner copper layers too.
DEFAULT_EXPORTED_LAYERS = {
    "F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS",
}

DEFAULT_LAYER_ORDER = [
    "F.Cu",
    # inner copper layers are inserted here
    "B.Cu",
    "F.Mask",
    "B.Mask",
    "F.Paste",
    "B.Paste",
    "F.SilkS",
    "B.SilkS",
    "F.Adhes",
    "B.Adhes",
    "F.Fab",
    "B.Fab",
    "F.CrtYd",
    "B.CrtYd",
]

COLOR_MODES = ("color", "bw")

# Layers grid columns
COL_EXPORT, COL_LAYER, COL_BACKGROUND, COL_EDGE, COL_MIRROR, COL_INVERT, COL_ROTATE = range(7)
GRID_COLUMNS = [
    (COL_EXPORT, "col_export"),
    (COL_LAYER, "col_layer"),
    (COL_BACKGROUND, "col_background"),
    (COL_EDGE, "col_edge"),
    (COL_MIRROR, "col_mirror"),
    (COL_INVERT, "col_invert"),
    (COL_ROTATE, "col_rotate"),
]
BOOL_COLUMNS = (COL_EXPORT, COL_BACKGROUND, COL_EDGE, COL_MIRROR, COL_INVERT, COL_ROTATE)

# BOM grid columns
BOM_INCLUDE, BOM_FIELD, BOM_LABEL, BOM_GROUP = range(4)
BOM_COLUMNS = [
    (BOM_INCLUDE, "bom_col_include"),
    (BOM_FIELD, "bom_col_field"),
    (BOM_LABEL, "bom_col_label"),
    (BOM_GROUP, "bom_col_group"),
]
BOM_BOOL_COLUMNS = (BOM_INCLUDE, BOM_GROUP)
# Column -> profile key
COLUMN_KEYS = {
    COL_EXPORT: "export",
    COL_BACKGROUND: "add_background",
    COL_EDGE: "add_edge_cuts",
    COL_INVERT: "invert_colors",
    COL_ROTATE: "rotate_180",
    COL_MIRROR: "mirror",
}

INNER_CU_RE = re.compile(r"^In(\d+)\.Cu$")


def default_layer_state(layer):
    return {
        "export": layer in DEFAULT_EXPORTED_LAYERS or bool(INNER_CU_RE.match(layer)),
        "add_background": True,
        "add_edge_cuts": False,
        "invert_colors": False,
        "rotate_180": False,
        "mirror": layer.startswith("B."),
    }


class ReleaseWizardDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title=tr("title"),
            size=(1050, 720),
            style=wx.DEFAULT_DIALOG_STYLE
            | wx.RESIZE_BORDER
            | wx.MAXIMIZE_BOX
            | wx.MINIMIZE_BOX,
        )

        self.project_dir = Path(pcbnew.GetBoard().GetFileName()).parent
        self.project_name = self.project_dir.name
        kicad_pro = list(self.project_dir.glob("*.kicad_pro"))
        if kicad_pro:
            self.project_name = kicad_pro[0].stem
        self.project_file = self.project_dir / (self.project_name + ".kicad_pro")
        self.profile_path = self.project_dir / "kicad_release_profile.json"

        self.layer_entries = self._read_layers()
        self.layer_rows = [entry["canonical"] for entry in self.layer_entries]

        root = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.StaticText(self, label=self._header_text())
        root.Add(self.header, 0, wx.ALL | wx.EXPAND, 8)

        nb = wx.Notebook(self)
        root.Add(nb, 1, wx.ALL | wx.EXPAND, 8)

        nb.AddPage(self._build_jobs_page(nb), tr("tab_jobs"))
        nb.AddPage(self._build_layers_page(nb), tr("tab_layers"))
        nb.AddPage(self._build_bom_page(nb), tr("tab_bom"))
        nb.AddPage(self._build_options_page(nb), tr("tab_options"))

        self._load_profile_into_ui()
        self._autosize_layers_grid()
        self._autosize_bom_grid()

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        save_profile = wx.Button(self, label=tr("btn_save_profile"))
        load_profile = wx.Button(self, label=tr("btn_load_profile"))
        gen = wx.Button(self, label=tr("btn_generate"))
        close = wx.Button(self, wx.ID_CANCEL, label=tr("btn_close"))
        save_profile.Bind(wx.EVT_BUTTON, self.on_save_profile)
        load_profile.Bind(wx.EVT_BUTTON, self.on_load_profile)
        gen.Bind(wx.EVT_BUTTON, self.on_generate)
        buttons.Add(save_profile, 0, wx.ALL, 5)
        buttons.Add(load_profile, 0, wx.ALL, 5)
        buttons.AddStretchSpacer()
        buttons.Add(gen, 0, wx.ALL, 5)
        buttons.Add(close, 0, wx.ALL, 5)
        root.Add(buttons, 0, wx.EXPAND)
        self.SetSizer(root)
        self.SetMinSize((760, 520))
        try:
            work = wx.Display(0).GetClientArea()
            self.SetSize(
                (
                    min(1120, max(760, work.width - 80)),
                    min(760, max(520, work.height - 80)),
                )
            )
        except Exception:
            pass
        self.CentreOnParent()
        wx.CallAfter(self._autosize_layers_grid)

    # ------------------------------------------------------------------ UI

    def _header_text(self):
        return tr(
            "header",
            project=self.project_name,
            folder=self.project_dir,
            profile=self.profile_path,
        )

    def _build_jobs_page(self, nb):
        panel = wx.Panel(nb)
        sizer = wx.BoxSizer(wx.VERTICAL)
        info = wx.StaticText(panel, label=tr("jobs_info"))
        sizer.Add(info, 0, wx.ALL, 5)
        self.job_checks = {}
        for job_id, default in DEFAULT_JOBS:
            cb = wx.CheckBox(panel, label=tr("job_" + job_id))
            cb.SetValue(default)
            cb.SetToolTip(tr("job_" + job_id + "_tip"))
            self.job_checks[job_id] = cb
            sizer.Add(cb, 0, wx.ALL, 4)
        panel.SetSizer(sizer)
        return panel

    def _build_layers_page(self, nb):
        panel = wx.Panel(nb)
        sizer = wx.BoxSizer(wx.VERTICAL)
        info = wx.StaticText(panel, label=tr("layers_info"))
        info.Wrap(900)
        sizer.Add(info, 0, wx.ALL, 5)

        formats = wx.BoxSizer(wx.HORIZONTAL)
        formats.Add(
            wx.StaticText(panel, label=tr("layer_formats")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            8,
        )
        self.format_checks = {}
        for fmt, default in LAYER_FORMATS:
            cb = wx.CheckBox(panel, label=tr("fmt_" + fmt))
            cb.SetValue(default)
            cb.SetToolTip(tr("fmt_" + fmt + "_tip"))
            self.format_checks[fmt] = cb
            formats.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        sizer.Add(formats, 0, wx.ALL, 5)

        grid = wxgrid.Grid(panel)
        self.layers_grid = grid
        grid.CreateGrid(len(self.layer_entries), len(GRID_COLUMNS))
        for col, key in GRID_COLUMNS:
            grid.SetColLabelValue(col, tr(key))
        grid.SetColLabelSize(int(grid.GetCharHeight() * 2.6))
        grid.SetRowLabelSize(42)
        grid.EnableEditing(True)
        for col in BOOL_COLUMNS:
            grid.SetColFormatBool(col)

        for row, entry in enumerate(self.layer_entries):
            grid.SetCellValue(row, COL_LAYER, entry["label"])
            grid.SetReadOnly(row, COL_LAYER, True)
            for col in BOOL_COLUMNS:
                grid.SetCellAlignment(row, col, wx.ALIGN_CENTER, wx.ALIGN_CENTER)
            self._apply_layer_state(row, default_layer_state(entry["canonical"]))

        grid.AutoSizeRows(False)
        grid.Bind(wxgrid.EVT_GRID_CELL_LEFT_CLICK, self.on_layers_grid_left_click)
        grid.Bind(wxgrid.EVT_GRID_LABEL_LEFT_CLICK, self.on_layers_label_click)
        grid.Bind(wx.EVT_SIZE, self.on_layers_grid_size)
        self._bind_col_tooltips(grid, GRID_COLUMNS)

        sizer.Add(grid, 1, wx.ALL | wx.EXPAND, 3)
        panel.SetSizer(sizer)
        return panel

    def _build_options_page(self, nb):
        panel = wx.Panel(nb)
        grid = wx.FlexGridSizer(0, 2, 8, 8)
        grid.AddGrowableCol(1)
        label = wx.StaticText(panel, label=tr("opt_color_mode"))
        self.color_mode = wx.Choice(panel, choices=[tr("opt_color"), tr("opt_bw")])
        self.color_mode.SetSelection(0)
        for w in (label, self.color_mode):
            w.SetToolTip(tr("opt_color_mode_tip"))
        grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.color_mode, 1, wx.EXPAND)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(grid, 0, wx.ALL | wx.EXPAND, 10)
        panel.SetSizer(outer)
        return panel

    def _autosize_layers_grid(self):
        """Size columns to their content (labels included)."""
        try:
            grid = self.layers_grid
            grid.AutoSizeColumns(setAsMin=False)
            for col in BOOL_COLUMNS:
                if grid.GetColSize(col) < 70:
                    grid.SetColSize(col, 70)
            grid.ForceRefresh()
        except Exception:
            pass

    def on_layers_grid_size(self, evt):
        wx.CallAfter(self._autosize_layers_grid)
        evt.Skip()

    def on_layers_grid_left_click(self, evt):
        """Single-click toggle for checkbox cells."""
        row = evt.GetRow()
        col = evt.GetCol()
        if row >= 0 and col in BOOL_COLUMNS:
            self._set_grid_bool(row, col, not self._grid_bool(row, col))
            if col == COL_EXPORT:
                self._refresh_row_style(row)
            return
        evt.Skip()

    def on_layers_label_click(self, evt):
        """Click on a checkbox column header: tick all rows, or untick all if all ticked."""
        col, row = evt.GetCol(), evt.GetRow()
        if row != -1 or col not in BOOL_COLUMNS:
            evt.Skip()
            return
        rows = range(self.layers_grid.GetNumberRows())
        value = not all(self._grid_bool(r, col) for r in rows)
        for r in rows:
            self._set_grid_bool(r, col, value)
            if col == COL_EXPORT:
                self._refresh_row_style(r)
        self.layers_grid.ForceRefresh()

    def _bind_col_tooltips(self, grid, columns):
        """Show a per-column tooltip on a grid header (i18n key <column key>_tip)."""
        state = {"col": None}
        win = grid.GetGridColLabelWindow()

        def on_motion(evt):
            x, _ = grid.CalcUnscrolledPosition(evt.GetX(), 0)
            col = grid.XToCol(x)
            if col != state["col"]:
                state["col"] = col
                if col == wx.NOT_FOUND or col < 0:
                    win.UnsetToolTip()
                else:
                    win.SetToolTip(tr(columns[col][1] + "_tip"))
            evt.Skip()

        win.Bind(wx.EVT_MOTION, on_motion)

    # ---------------------------------------------------------------- BOM

    def _build_bom_page(self, nb):
        panel = wx.Panel(nb)
        sizer = wx.BoxSizer(wx.VERTICAL)
        info = wx.StaticText(panel, label=tr("bom_info"))
        info.Wrap(900)
        sizer.Add(info, 0, wx.ALL, 5)

        body = wx.BoxSizer(wx.HORIZONTAL)
        grid = wxgrid.Grid(panel)
        self.bom_grid = grid
        grid.CreateGrid(0, len(BOM_COLUMNS))
        for col, key in BOM_COLUMNS:
            grid.SetColLabelValue(col, tr(key))
        grid.SetRowLabelSize(42)
        grid.Bind(wxgrid.EVT_GRID_CELL_LEFT_CLICK, self.on_bom_grid_left_click)
        self._bind_col_tooltips(grid, BOM_COLUMNS)
        body.Add(grid, 1, wx.ALL | wx.EXPAND, 3)

        buttons = wx.BoxSizer(wx.VERTICAL)
        for key, handler in (
            ("bom_btn_up", self.on_bom_up),
            ("bom_btn_down", self.on_bom_down),
            ("bom_btn_reset", self.on_bom_reset),
        ):
            btn = wx.Button(panel, label=tr(key))
            btn.SetToolTip(tr(key + "_tip"))
            btn.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(btn, 0, wx.ALL | wx.EXPAND, 3)
        body.Add(buttons, 0, wx.ALL, 3)
        sizer.Add(body, 1, wx.EXPAND)

        panel.SetSizer(sizer)
        self._set_bom_rows(default_bom_fields(self.project_dir))
        return panel

    def _set_bom_rows(self, rows):
        grid = self.bom_grid
        if grid.GetNumberRows():
            grid.DeleteRows(0, grid.GetNumberRows())
        grid.AppendRows(len(rows))
        for r, row in enumerate(rows):
            self._write_bom_row(r, row)
        self._autosize_bom_grid()

    def _write_bom_row(self, r, row):
        grid = self.bom_grid
        grid.SetCellValue(r, BOM_INCLUDE, "1" if row["include"] else "0")
        grid.SetCellValue(r, BOM_FIELD, row["field"])
        grid.SetReadOnly(r, BOM_FIELD, True)
        grid.SetCellValue(r, BOM_LABEL, row["label"])
        grid.SetCellValue(r, BOM_GROUP, "1" if row["group_by"] else "0")
        for col in BOM_BOOL_COLUMNS:
            # Per-cell bool renderer: rows are rebuilt on reorder / reset.
            grid.SetCellRenderer(r, col, wxgrid.GridCellBoolRenderer())
            grid.SetReadOnly(r, col, True)  # toggled by single click
            grid.SetCellAlignment(r, col, wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        bg = (
            grid.GetDefaultCellBackgroundColour()
            if row["include"]
            else wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
        )
        for col in (BOM_FIELD, BOM_LABEL, BOM_GROUP):
            grid.SetCellBackgroundColour(r, col, bg)
        grid.ForceRefresh()

    def _read_bom_row(self, r):
        grid = self.bom_grid
        truthy = ("1", "true", "True")
        return {
            "field": grid.GetCellValue(r, BOM_FIELD),
            "include": grid.GetCellValue(r, BOM_INCLUDE) in truthy,
            "label": grid.GetCellValue(r, BOM_LABEL).strip(),
            "group_by": grid.GetCellValue(r, BOM_GROUP) in truthy,
        }

    def _bom_rows(self):
        if self.bom_grid.IsCellEditControlEnabled():
            self.bom_grid.SaveEditControlValue()
            self.bom_grid.DisableCellEditControl()
        return [self._read_bom_row(r) for r in range(self.bom_grid.GetNumberRows())]

    def _autosize_bom_grid(self):
        try:
            grid = self.bom_grid
            grid.AutoSizeColumns(setAsMin=False)
            for col in BOM_BOOL_COLUMNS:
                if grid.GetColSize(col) < 70:
                    grid.SetColSize(col, 70)
            if grid.GetColSize(BOM_LABEL) < 220:
                grid.SetColSize(BOM_LABEL, 220)
            grid.ForceRefresh()
        except Exception:
            pass

    def on_bom_grid_left_click(self, evt):
        row, col = evt.GetRow(), evt.GetCol()
        if row >= 0 and col in BOM_BOOL_COLUMNS:
            data = self._read_bom_row(row)
            key = "include" if col == BOM_INCLUDE else "group_by"
            data[key] = not data[key]
            self._write_bom_row(row, data)
            self.bom_grid.SetGridCursor(row, BOM_FIELD)
            return
        evt.Skip()

    def _move_bom_row(self, delta):
        grid = self.bom_grid
        rows = self._bom_rows()
        r = grid.GetGridCursorRow()
        target = r + delta
        if r < 0 or not (0 <= target < len(rows)):
            return
        rows[r], rows[target] = rows[target], rows[r]
        self._write_bom_row(r, rows[r])
        self._write_bom_row(target, rows[target])
        grid.SetGridCursor(target, grid.GetGridCursorCol())
        grid.MakeCellVisible(target, 0)

    def on_bom_up(self, _evt):
        self._move_bom_row(-1)

    def on_bom_down(self, _evt):
        self._move_bom_row(1)

    def on_bom_reset(self, _evt):
        self._set_bom_rows(default_bom_fields(self.project_dir))

    # ------------------------------------------------------------- layers

    def _pcb_file(self):
        pcb_file = self.project_dir / (self.project_name + ".kicad_pcb")
        if not pcb_file.exists():
            found = list(self.project_dir.glob("*.kicad_pcb"))
            if found:
                pcb_file = found[0]
        return pcb_file

    def _read_layers(self):
        pcb_file = self._pcb_file()

        entries = []
        seen = set()

        def make_label(canonical: str, display: str) -> str:
            display = (display or "").strip()
            if display and display != canonical:
                return f"{canonical} ({display})"
            return canonical

        try:
            text = pcb_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"(?s)\(layers\s+(.*?)\)\s*\(setup", text)
            if m:
                for lm in re.finditer(
                    r'\(\s*(\d+)\s+"([^"]+)"\s+([^\s\)]+)(?:\s+"([^"]+)")?\s*\)',
                    m.group(1),
                ):
                    canonical = lm.group(2)
                    # Dwgs.User / Edge.Cuts are added through the per-layer options and
                    # Edge.Cuts is always part of the Gerbers.
                    if canonical in seen or canonical in ("Dwgs.User", "Edge.Cuts"):
                        continue
                    seen.add(canonical)
                    entries.append(
                        {
                            "index": int(lm.group(1)),
                            "canonical": canonical,
                            "label": make_label(canonical, lm.group(4) or ""),
                        }
                    )
        except Exception:
            pass

        inner = sorted(
            (e for e in entries if INNER_CU_RE.match(e["canonical"])),
            key=lambda e: int(INNER_CU_RE.match(e["canonical"]).group(1)),
        )
        order = ["F.Cu"] + [e["canonical"] for e in inner] + DEFAULT_LAYER_ORDER[1:]
        by_name = {e["canonical"]: e for e in entries}
        preferred = [by_name[n] for n in order if n in by_name]
        rest = [e for e in entries if e not in preferred]
        return preferred + rest

    def _grid_bool(self, row, col):
        return self.layers_grid.GetCellValue(row, col) in ("1", "true", "True")

    def _set_grid_bool(self, row, col, value):
        self.layers_grid.SetCellValue(row, col, "1" if value else "0")

    def _apply_layer_state(self, row, state):
        for col, key in COLUMN_KEYS.items():
            self._set_grid_bool(row, col, bool(state.get(key)))
        self._refresh_row_style(row)

    def _refresh_row_style(self, row):
        """Grey out the PDF options of layers that are not exported."""
        grid = self.layers_grid
        enabled = self._grid_bool(row, COL_EXPORT)
        bg = (
            grid.GetDefaultCellBackgroundColour()
            if enabled
            else wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
        )
        for col in range(len(GRID_COLUMNS)):
            if col != COL_EXPORT:
                grid.SetCellBackgroundColour(row, col, bg)
        grid.ForceRefresh()

    def _layer_state(self, row):
        return {key: self._grid_bool(row, col) for col, key in COLUMN_KEYS.items()}

    def _selected_layers(self):
        return [
            layer
            for row, layer in enumerate(self.layer_rows)
            if self._grid_bool(row, COL_EXPORT)
        ]

    def _selected_layer_options(self):
        options = []
        for row, layer in enumerate(self.layer_rows):
            state = self._layer_state(row)
            if not state.pop("export"):
                continue
            options.append(dict(layer=layer, **state))
        return options

    def _selected_jobs(self):
        return {k: cb.GetValue() for k, cb in self.job_checks.items()}

    def _selected_formats(self):
        return [fmt for fmt, _ in LAYER_FORMATS if self.format_checks[fmt].GetValue()]

    def _color_mode(self):
        return COLOR_MODES[max(0, self.color_mode.GetSelection())]

    # ------------------------------------------------------------ profile

    def _profile_dict(self):
        """Return the complete UI profile saved at project root."""
        return {
            "version": PROFILE_VERSION,
            "project_name": self.project_name,
            "jobs": self._selected_jobs(),
            "layer_formats": self._selected_formats(),
            "layers": [
                dict(layer=layer, **self._layer_state(row))
                for row, layer in enumerate(self.layer_rows)
            ],
            "bom_fields": self._bom_rows(),
            "options": {"color_mode": self._color_mode()},
        }

    def _save_profile(self, path=None):
        target = Path(path) if path else self.profile_path
        target.write_text(
            json.dumps(self._profile_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.profile_path = target
        self.header.SetLabel(self._header_text())
        return target

    def _load_profile_file(self, path: Path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            wx.MessageBox(
                tr("msg_profile_read_error", path=path, error=e),
                tr("msg_profile_title"),
                wx.OK | wx.ICON_WARNING,
            )
            return False

        self.profile_path = Path(path)
        self.header.SetLabel(self._header_text())

        jobs = data.get("jobs", {})
        if isinstance(jobs, dict):
            for job_id, cb in self.job_checks.items():
                if job_id in jobs:
                    cb.SetValue(bool(jobs[job_id]))

        formats = data.get("layer_formats")
        if isinstance(formats, list):
            for fmt, cb in self.format_checks.items():
                cb.SetValue(fmt in formats)

        layer_state = {}
        for item in data.get("layers") or []:
            if isinstance(item, dict) and item.get("layer"):
                layer_state[str(item["layer"])] = item
        for row, layer in enumerate(self.layer_rows):
            item = layer_state.get(layer)
            if not item:
                continue
            state = default_layer_state(layer)
            for key in state:
                if key in item:
                    state[key] = bool(item[key])
            self._apply_layer_state(row, state)

        if isinstance(data.get("bom_fields"), list):
            self._set_bom_rows(
                merge_bom_fields(data["bom_fields"], default_bom_fields(self.project_dir))
            )

        opts = data.get("options", {})
        if isinstance(opts, dict) and opts.get("color_mode") in COLOR_MODES:
            self.color_mode.SetSelection(COLOR_MODES.index(opts["color_mode"]))
        return True

    def _load_profile_into_ui(self):
        """Load kicad_release_profile.json from project root if it exists."""
        if self.profile_path.exists():
            self._load_profile_file(self.profile_path)

    # ---------------------------------------------------------- generate

    def _write_file(self, path: Path, content: str, overwrite: bool):
        if path.exists() and not overwrite:
            return False
        path.write_text(content, encoding="utf-8")
        return True

    def generate_files(self):
        jobs = self._selected_jobs()
        formats = self._selected_formats()
        selected_layers = self._selected_layers()
        if not selected_layers and (formats or jobs.get("pcb_pdf")):
            raise RuntimeError(tr("msg_no_layer"))
        bom_fields = [row for row in self._bom_rows() if row["include"]]
        if jobs.get("bom_csv") and not bom_fields:
            raise RuntimeError(tr("msg_no_bom_field"))

        release = self.project_dir / "release"

        # Remove previous outputs but keep the release/ folder itself.
        if release.exists():
            for item in release.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        release.mkdir(exist_ok=True)

        scripts_dir = self.project_dir / ".scripts"
        scripts_dir.mkdir(exist_ok=True)
        # Job scripts are always rewritten.
        for src in JOB_SCRIPTS_DIR.glob("*.py"):
            shutil.copyfile(src, scripts_dir / src.name)

        self._save_profile()

        selected_layer_options = self._selected_layer_options()

        cli = find_kicad_cli()
        if not cli:
            raise RuntimeError(tr("msg_kicad_cli_not_found"))
        python, has_pymupdf = find_python()
        if not python:
            raise RuntimeError(tr("msg_python_not_found"))
        needs_pymupdf = jobs.get("drill_map_pdf") or (
            "pdf" in formats
            and any(o["invert_colors"] or o["rotate_180"] for o in selected_layer_options)
        )
        if needs_pymupdf and not has_pymupdf:
            raise RuntimeError(tr("msg_pymupdf_missing", python=python))

        # PDF inversion uses the exact board outline (cut-outs included) from pcbnew.
        outline_json = scripts_dir / "board_outline.json"
        if outline_json.exists():
            outline_json.unlink()
        if "pdf" in formats and any(o["invert_colors"] for o in selected_layer_options):
            try:
                write_board_outline(self._pcb_file(), outline_json)
            except Exception as e:
                raise RuntimeError(tr("msg_outline_error", error=e))

        # Settings of the job scripts (release_jobs.py).
        (scripts_dir / "release_config.json").write_text(
            json.dumps(
                {
                    "root": str(self.project_dir),
                    "project": self.project_name,
                    "pcb": str(self._pcb_file()),
                    "sch": str(self._sch_file() or ""),
                    "kicad_cli": cli,
                    "color_mode": self._color_mode(),
                    "layers": selected_layers,
                    "layer_options": selected_layer_options,
                    "layer_formats": formats,
                    "debug": False,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        cfg = {
            "jobs": jobs,
            "layer_formats": formats,
            "bom_fields": bom_fields,
            "layers": selected_layers,
        }
        jobset = build_jobset(cfg, command_path(python))
        jobset_path = release / "kicad_release.kicad_jobset"
        jobset_path.write_text(json.dumps(jobset, indent=2), encoding="utf-8")
        self._kicad_cli = cli
        return jobset_path

    def _sch_file(self):
        sch = self.project_dir / (self.project_name + ".kicad_sch")
        if sch.is_file():
            return sch
        found = sorted(self.project_dir.glob("*.kicad_sch"))
        return found[0] if found else None

    def on_save_profile(self, _evt):
        try:
            with wx.FileDialog(
                self,
                tr("dlg_save_profile"),
                defaultDir=str(self.project_dir),
                defaultFile="kicad_release_profile.json",
                wildcard=tr("wildcard_json"),
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                target = self._save_profile(Path(dlg.GetPath()))
                wx.MessageBox(
                    tr("msg_profile_saved", path=target),
                    tr("title"),
                    wx.OK | wx.ICON_INFORMATION,
                )
        except Exception as e:
            wx.MessageBox(str(e), tr("msg_error"), wx.OK | wx.ICON_ERROR)

    def on_load_profile(self, _evt):
        try:
            with wx.FileDialog(
                self,
                tr("dlg_load_profile"),
                defaultDir=str(self.project_dir),
                defaultFile="kicad_release_profile.json",
                wildcard=tr("wildcard_json"),
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                path = Path(dlg.GetPath())
                if self._load_profile_file(path):
                    wx.MessageBox(
                        tr("msg_profile_loaded", path=path),
                        tr("title"),
                        wx.OK | wx.ICON_INFORMATION,
                    )
        except Exception as e:
            wx.MessageBox(str(e), tr("msg_error"), wx.OK | wx.ICON_ERROR)

    def on_generate(self, _evt):
        """Write scripts + jobset, save the profile, then run the jobset with a live log."""
        try:
            jobset = self.generate_files()
        except Exception as e:
            wx.MessageBox(str(e), tr("msg_error"), wx.OK | wx.ICON_ERROR)
            return
        cmd = [self._kicad_cli, "jobset", "run", "--file", str(jobset), str(self.project_file)]
        dlg = RunLogDialog(self, cmd, self.project_dir)
        dlg.ShowModal()
        dlg.Destroy()


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class RunLogDialog(wx.Dialog):
    """Runs kicad-cli and shows its output live (same on Windows, macOS and Linux)."""

    def __init__(self, parent, cmd, cwd):
        super().__init__(
            parent,
            title=tr("run_title"),
            size=(980, 640),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
        )
        self.release_dir = Path(cwd) / "release"
        self.status = wx.StaticText(self, label=tr("run_running"))
        self.text = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL
        )
        self.text.SetFont(
            wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        )
        self.stop_btn = wx.Button(self, label=tr("btn_stop"))
        open_btn = wx.Button(self, label=tr("btn_open_release"))
        close_btn = wx.Button(self, wx.ID_CANCEL, label=tr("btn_close"))
        self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop)
        open_btn.Bind(wx.EVT_BUTTON, self.on_open_release)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        close_btn.Bind(wx.EVT_BUTTON, self.on_close)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.Add(self.stop_btn, 0, wx.ALL, 5)
        buttons.Add(open_btn, 0, wx.ALL, 5)
        buttons.AddStretchSpacer()
        buttons.Add(close_btn, 0, wx.ALL, 5)
        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(self.status, 0, wx.ALL | wx.EXPAND, 8)
        root.Add(self.text, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 8)
        root.Add(buttons, 0, wx.ALL | wx.EXPAND, 4)
        self.SetSizer(root)
        self.CentreOnParent()

        self.running = True
        self.text.AppendText(" ".join(cmd) + "\n\n")
        self.proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for raw in iter(self.proc.stdout.readline, b""):
            line = ANSI_RE.sub("", raw.decode("utf-8", errors="replace")).rstrip()
            wx.CallAfter(self._append, line)
        wx.CallAfter(self._finished, self.proc.wait())

    def _append(self, line):
        if self:  # the dialog may already be destroyed
            self.text.AppendText(line + "\n")

    def _finished(self, code):
        if not self:
            return
        self.running = False
        self.stop_btn.Disable()
        self.status.SetLabel(tr("run_ok") if code == 0 else tr("run_failed", code=code))

    def _kill(self):
        if self.running and self.proc.poll() is None:
            self.proc.kill()

    def on_stop(self, _evt):
        self._kill()
        self.status.SetLabel(tr("run_stopped"))

    def on_close(self, _evt):
        self._kill()
        self.EndModal(wx.ID_CANCEL)

    def on_open_release(self, _evt):
        path = str(self.release_dir)
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            wx.MessageBox(str(e), tr("msg_error"), wx.OK | wx.ICON_ERROR)


def build_jobset(cfg, python):
    """KiCad jobset. Script steps run "<python> .scripts/release_jobs.py <job>" from the
    project folder (special_execute commands may not contain quotes)."""
    jobs_enabled = cfg["jobs"]
    layers = cfg["layers"]
    formats = cfg.get("layer_formats", [])
    jobs = []

    def script_job(desc, jid, job):
        return {
            "description": desc,
            "id": jid,
            "settings": {
                "command": f"{python} .scripts/release_jobs.py {job}",
                "description": "",
                "ignore_exit_code": False,
                "output_filename": "",
                "record_output": False,
            },
            "type": "special_execute",
        }

    if jobs_enabled.get("erc", True):
        jobs.append(
            {
                "description": "ERC",
                "id": "erc",
                "settings": {
                    "description": "",
                    "fail_on_error": True,
                    "format": "report",
                    "output_filename": "${PROJECTNAME}_ERC.txt",
                    "severity": 48,
                    "units": "mm",
                },
                "type": "sch_erc",
            }
        )
    if jobs_enabled.get("drc", True):
        jobs.append(
            {
                "description": "DRC",
                "id": "drc",
                "settings": {
                    "description": "",
                    "fail_on_error": True,
                    "format": "report",
                    "output_filename": "${PROJECTNAME}_DRC.txt",
                    "parity": True,
                    "refill_zones": False,
                    "report_all_track_errors": True,
                    "save_board": False,
                    "severity": 48,
                    "units": "mm",
                },
                "type": "pcb_drc",
            }
        )
    if jobs_enabled.get("pcb_implantation", True):
        jobs.append(script_job("PCB IMPLANTATION", "pcb_implantation", "implantation"))
    if jobs_enabled.get("sch_pdf", True):
        jobs.append(script_job("SCH PDF", "sch_pdf", "sch_pdf"))
    if jobs_enabled.get("pcb_pdf", True):
        jobs.append(script_job("PCB PDF", "pcb_pdf", "pcb_pdf"))
    scripted = [f for f in SCRIPTED_LAYER_FORMATS if f in formats]
    if scripted:
        jobs.append(
            script_job("PCB LAYERS " + "/".join(f.upper() for f in scripted), "pcb_layers", "layers")
        )
    if jobs_enabled.get("drill_map_pdf", True):
        jobs.append(script_job("DRILL MAP PDF", "drill_map_pdf", "drill_map"))
    if jobs_enabled.get("bom_csv", True):
        jobs.append(bom_job(cfg.get("bom_fields", [])))
    if jobs_enabled.get("pnp_csv", True):
        jobs.append(pnp_job())
    if jobs_enabled.get("pcb_drill", True):
        jobs.append(drill_job())
    if "gerber" in formats:
        jobs.append(gerber_job(layers))
        jobs.append(script_job("GERBER EXTENSIONS", "pcb_gerber_extensions", "gerber_ext"))
    if jobs_enabled.get("meca_step", True):
        jobs.append(step_job())

    present = {j["id"] for j in jobs}
    outputs = []

    def add_output(oid, ids, path, archive=False):
        only = [x for x in ids if x in present]
        if not only:  # an empty "only" list would run every job
            return
        out = {"description": oid, "id": oid, "only": only, "type": "folder",
               "settings": {"output_path": path}}
        if archive:
            out["type"] = "archive"
            out["settings"]["format"] = "zip"
        outputs.append(out)

    grb = ["pcb_gerbers", "pcb_gerber_extensions", "pcb_drill"]
    add_output("01_PCB_GRB", grb, "${KIPRJMOD}/release/01_PCB/GRB")
    add_output("01_PCB_LAYERS", ["pcb_layers", "drill_map_pdf"], "${KIPRJMOD}/release/01_PCB")
    add_output("02_PCBA", ["pcb_implantation", "bom_csv", "pnp_csv"], "${KIPRJMOD}/release/02_PCBA")
    add_output("03_DOCS", ["erc", "drc", "sch_pdf", "pcb_pdf"], "${KIPRJMOD}/release/03_DOCS")
    add_output("04_MECA", ["meca_step"], "${KIPRJMOD}/release/04_MECA")
    if jobs_enabled.get("zip_gerber", True) and "gerber" in formats:
        add_output(
            "GERBER", grb,
            "${KIPRJMOD}/release/01_PCB/GRB/${PROJECTNAME}_GERBER.zip", archive=True,
        )
    return {"jobs": jobs, "meta": {"version": 1}, "outputs": outputs}


def bom_job(fields):
    """BOM job from the BOM tab rows (only the included ones, in column order)."""
    names = [f["field"] for f in fields]
    sort_field = "Reference" if "Reference" in names else (names[0] if names else "Reference")
    return {
        "description": "BOM",
        "id": "bom_csv",
        "settings": {
            "bom_format_preset_name": "",
            "bom_preset_name": "",
            "description": "",
            "exclude_dnp": True,
            "field_delimiter": ";",
            "fields_group_by": [f["field"] for f in fields if f.get("group_by")],
            "fields_labels": [f.get("label") or f["field"] for f in fields],
            "fields_ordered": names,
            "filter_string": "",
            "group_symbols": any(f.get("group_by") for f in fields),
            "keep_line_breaks": False,
            "keep_tabs": False,
            "output_filename": "${PROJECTNAME}_BOM.csv",
            "ref_delimiter": ",",
            "ref_range_delimiter": "-",
            "sort_asc": True,
            "sort_field": sort_field,
            "string_delimiter": '"',
            "variant_names": [],
        },
        "type": "sch_export_bom",
    }


def pnp_job():
    return {
        "description": "PNP",
        "id": "pnp_csv",
        "settings": {
            "description": "",
            "exclude_bom": False,
            "exclude_dnp": True,
            "exclude_footprints_with_th": False,
            "format": "csv",
            "gerber_board_edge": True,
            "negate_bottom_x": False,
            "output_filename": "${PROJECTNAME}_POS.csv",
            "side": "both",
            "single_file": True,
            "smd_only": False,
            "units": "mm",
            "use_drill_place_file_origin": True,
            "variant": "",
        },
        "type": "pcb_export_pos",
    }


def drill_job():
    return {
        "description": "PCB DRILL",
        "id": "pcb_drill",
        "settings": {
            "description": "",
            "drill_origin": "abs",
            "excellon.combine_pth_npth": True,
            "excellon.minimal_header": False,
            "excellon.mirror_y": False,
            "excellon.oval_drill_route": False,
            "format": "excellon",
            "generate_map": False,
            "generate_report": False,
            "generate_tenting": False,
            "gerber_precision": 5,
            "map_format": "pdf",
            "output_dir": ".",
            "report_filename": "",
            "units": "mm",
            "zero_format": "decimal",
        },
        "type": "pcb_export_drill",
    }


def gerber_job(selected_layers):
    """Gerbers of the layers ticked in the Layers tab; Edge.Cuts is always included.

    X2 format, coordinates 4.6 in mm (precision 6).
    """
    layers = [layer for layer in selected_layers if layer != "Edge.Cuts"]
    layers.append("Edge.Cuts")

    # use_protel_file_extension=True lets KiCad emit the usual extensions for
    # standard layers. The post-processing job pcb_gerber_extensions then
    # enforces / normalizes the requested extension list, including inner layers.
    return {
        "description": "PCB GERBER",
        "id": "pcb_gerbers",
        "settings": {
            "black_and_white": True,
            "check_zones": False,
            "create_gerber_job_file": True,
            "crossout_dnp_footprints_on_fab_layers": True,
            "description": "",
            "disable_aperture_macros": False,
            "drawing_sheet": "",
            "drill_shape": "full",
            "hide_dnp_footprints_on_fab_layers": False,
            "include_netlist_attributes": True,
            "layers": layers,
            "layers_to_include_on_all_layers": [],
            "mirror": False,
            "negative": False,
            "output_filename": "",
            "plot_drawing_sheet": False,
            "plot_footprint_values": False,
            "plot_pad_numbers": False,
            "plot_ref_des": True,
            "precision": 6,
            "sketch_dnp_footprints_on_fab_layers": True,
            "sketch_pads_on_fab_layers": False,
            "subtract_solder_mask_from_silk": True,
            "use_drill_origin": False,
            "use_protel_file_extension": True,
            "use_x2_format": True,
        },
        "type": "pcb_export_gerbers",
    }


def step_job():
    return {
        "description": "STEP",
        "id": "meca_step",
        "settings": {
            "board_only": False,
            "board_outlines_chaining_epsilon": 0.01,
            "cut_vias_in_body": False,
            "description": "",
            "export_board_body": True,
            "export_components": True,
            "export_inner_copper": False,
            "export_pads": False,
            "export_silkscreen": True,
            "export_soldermask": True,
            "export_tracks": False,
            "export_zones": False,
            "fill_all_vias": False,
            "format": "step",
            "fuse_shapes": False,
            "include_dnp": True,
            "include_unspecified": True,
            "occt_format": 0,
            "optimize_step": True,
            "output_filename": "${PROJECTNAME}_STEP.step",
            "overwrite": True,
            "subst_models": True,
            "use_defined_origin": False,
            "use_drill_origin": False,
            "use_grid_origin": False,
            "use_pcb_center_origin": True,
            "user_origin.x": 180.0,
            "user_origin.y": 145.5,
            "vrml_model_dir": "",
            "vrml_relative_paths": False,
        },
        "type": "pcb_export_3d",
    }
