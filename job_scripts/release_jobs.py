"""Kicad Release Wizard - job runner, called by the generated .kicad_jobset.

    python release_jobs.py <job>

Settings are read from release_config.json next to this file (written by the
plugin on "Generate"). Standard library only; PyMuPDF (pdf_tools) is imported
only by the steps that post-process PDFs. Works on Windows, macOS and Linux.

Files are written to $JOBSET_OUTPUT_WORK_PATH, the folder where KiCad prepares
the current jobset output before copying / zipping it (fallback: release/...).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_LOG_FILE = None


def log(message):
    line = time.strftime("[%H:%M:%S] ") + str(message)
    print(line, flush=True)
    if _LOG_FILE is not None:
        _LOG_FILE.write(line + "\n")
        _LOG_FILE.flush()


def out_dir(cfg, fallback):
    """Output folder of the running jobset output, or release/<fallback> when run by hand."""
    work = os.environ.get("JOBSET_OUTPUT_WORK_PATH")
    path = Path(work) if work else cfg.release / fallback
    path.mkdir(parents=True, exist_ok=True)
    return path


class Config:
    def __init__(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.root = Path(data["root"])
        self.project = data["project"]
        self.pcb = Path(data["pcb"])
        self.sch = Path(data["sch"]) if data.get("sch") else None
        self.cli = data["kicad_cli"]
        self.color_mode = data.get("color_mode", "color")
        self.layers = list(data.get("layers", []))
        self.layer_options = {o["layer"]: o for o in data.get("layer_options", [])}
        self.formats = list(data.get("layer_formats", []))
        self.outline_json = HERE / "board_outline.json"
        self.debug = bool(data.get("debug", False))
        self.release = self.root / "release"

    @property
    def bw_args(self):
        return ["--black-and-white"] if self.color_mode == "bw" else []


def run_cli(cfg, args, output=None):
    """Run kicad-cli; its output goes to our stdout (jobset console and <job>.log)."""
    log("kicad-cli " + " ".join(f'"{a}"' if " " in str(a) else str(a) for a in args))
    res = subprocess.run(
        [cfg.cli] + [str(a) for a in args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in (res.stdout or "").splitlines():
        if line.strip():
            log("  " + line)
    if res.returncode != 0:
        raise RuntimeError(f"kicad-cli failed (exit code {res.returncode})")
    if output is not None and not Path(output).is_file():
        raise RuntimeError(f"kicad-cli did not create {output}")


def board_layers(pcb):
    """[(canonical, type, user name)] from the board's (layers ...) block."""
    text = Path(pcb).read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"(?s)\(layers\s+(.*?)\)\s*\(setup", text)
    if not m:
        raise RuntimeError("Unable to find the layers block in the .kicad_pcb file")
    return [
        (lm.group(2), lm.group(3), lm.group(4) or "")
        for lm in re.finditer(
            r'\(\s*(\d+)\s+"([^"]+)"\s+([^\s\)]+)(?:\s+"([^"]+)")?\s*\)', m.group(1)
        )
    ]


def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name).replace(".", "_")
    return re.sub(r"\s+", "_", name)


def layer_file_base(layer, layers):
    """Output file base name: the layer's user name when it has one."""
    for canonical, _kind, display in layers:
        if canonical == layer and display.strip() and display.strip() != layer:
            return safe_name(display.strip())
    return safe_name(layer)


def mkdir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


# -------------------------------------------------------------------- documents

def job_sch_pdf(cfg):
    if cfg.sch is None or not cfg.sch.is_file():
        raise RuntimeError("No .kicad_sch found")
    out = out_dir(cfg, "03_DOCS") / f"{cfg.project}_SCH.pdf"
    run_cli(cfg, ["sch", "export", "pdf", *cfg.bw_args, "--output", out, cfg.sch], out)


def job_pcb_pdf(cfg):
    known = {c for c, _k, _d in board_layers(cfg.pcb)}
    pages = []
    for layer in cfg.layers + ["Edge.Cuts"]:
        if layer not in known:
            log(f"WARN layer not in board, skipped: {layer}")
        elif layer not in pages:
            pages.append(layer)
    if not pages:
        raise RuntimeError("No layer to plot")
    out = out_dir(cfg, "03_DOCS") / f"{cfg.project}_PCB.pdf"
    run_cli(
        cfg,
        ["pcb", "export", "pdf", "--mode-multipage", "--include-border-title", *cfg.bw_args,
         "--layers", ",".join(pages), "--output", out, cfg.pcb],
        out,
    )


def job_implantation(cfg):
    folder = out_dir(cfg, "02_PCBA")
    top = folder / f"{cfg.project}_IMPLANT_TOP.pdf"
    bot = folder / f"{cfg.project}_IMPLANT_BOT.pdf"
    run_cli(cfg, ["pcb", "export", "pdf", "--mode-single", *cfg.bw_args,
                  "--layers", "F.Fab,Dwgs.User,Edge.Cuts", "--output", top, cfg.pcb], top)
    run_cli(cfg, ["pcb", "export", "pdf", "--mode-single", *cfg.bw_args, "--mirror",
                  "--layers", "B.Fab,Dwgs.User,Edge.Cuts", "--output", bot, cfg.pcb], bot)


def job_drill_map(cfg):
    out = mkdir(out_dir(cfg, "01_PCB") / "PDF") / f"{cfg.project}_DRILL_MAP.pdf"
    log("Drill map: vector drill marks at absolute coordinates + 4 mm F.Cu camera fiducials")
    res = subprocess.run(
        [sys.executable, str(HERE / "drill_map_pdf.py"), "--pcb", str(cfg.pcb), "--output", str(out)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
    )
    for line in (res.stdout or "").splitlines():
        log("  " + line)
    if res.returncode != 0 or not out.is_file():
        raise RuntimeError("Drill map generation failed")


# ----------------------------------------------------------------- PCB layers

def job_layers(cfg):
    """One file per selected layer and per format (PDF / SVG / DXF)."""
    layers_info = board_layers(cfg.pcb)
    known = {c for c, _k, _d in layers_info}
    formats = [f for f in ("pdf", "svg", "dxf") if f in cfg.formats]
    log(f"Formats={','.join(formats)} colour mode={cfg.color_mode}")
    base_dir = out_dir(cfg, "01_PCB")
    dirs = {f: mkdir(base_dir / f.upper()) for f in formats}

    for layer in cfg.layers:
        if layer not in known:
            log(f"WARN layer not in board, skipped: {layer}")
            continue
        opts = cfg.layer_options.get(layer, {})
        base = layer_file_base(layer, layers_info)
        decor = []
        if opts.get("add_background", True):
            decor.append("Dwgs.User")
        if opts.get("add_edge_cuts", False):
            decor.append("Edge.Cuts")
        layer_arg = ",".join([layer] + decor)
        mirror = ["--mirror"] if opts.get("mirror", False) else []
        log(f"Layer {layer} -> {base} (layers={layer_arg}, mirror={bool(mirror)}, "
            f"invert={opts.get('invert_colors', False)}, rotate={opts.get('rotate_180', False)})")

        if "svg" in dirs:
            out = dirs["svg"] / f"{base}.svg"
            run_cli(cfg, ["pcb", "export", "svg", "--mode-single", "--exclude-drawing-sheet",
                          "--page-size-mode", "0", *cfg.bw_args, *mirror,
                          "--layers", layer_arg, "--output", out, cfg.pcb], out)
        if "dxf" in dirs:
            # kicad-cli has no mirror / colour option for DXF.
            out = dirs["dxf"] / f"{base}.dxf"
            run_cli(cfg, ["pcb", "export", "dxf", "--mode-single", "--output-units", "mm",
                          "--use-contours", "--layers", layer_arg, "--output", out, cfg.pcb], out)
        if "pdf" in dirs:
            export_layer_pdf(cfg, layer, layer_arg, decor, mirror, opts, dirs["pdf"] / f"{base}.pdf")


def export_layer_pdf(cfg, layer, layer_arg, decor, mirror, opts, final_pdf):
    # Intermediate files live outside the output folder (it is copied as is by KiCad).
    tmp = Path(tempfile.mkdtemp(prefix="krw_"))
    stem = final_pdf.stem
    try:
        if opts.get("invert_colors", False):
            import pdf_tools

            if not cfg.outline_json.is_file():
                raise RuntimeError(
                    f"{cfg.outline_json} not found - run Generate from the Kicad Release Wizard plugin"
                )
            # The layer alone is inverted (always black & white); Dwgs.User / Edge.Cuts
            # are exported separately and drawn on top unchanged.
            raw = tmp / f"{stem}_RAW_LAYER.pdf"
            run_cli(cfg, ["pcb", "export", "pdf", "--mode-single", "--black-and-white", *mirror,
                          "--layers", layer, "--output", raw, cfg.pcb], raw)
            overlay = None
            if decor:
                overlay = tmp / f"{stem}_RAW_DECOR.pdf"
                run_cli(cfg, ["pcb", "export", "pdf", "--mode-single", "--black-and-white", *mirror,
                              "--layers", ",".join(decor), "--output", overlay, cfg.pcb], overlay)
            current = tmp / f"{stem}_INVERTED.pdf"
            pdf_tools.invert_pdf(raw, cfg.outline_json, current, bool(mirror), overlay, log=log)
        else:
            current = tmp / f"{stem}.pdf"
            run_cli(cfg, ["pcb", "export", "pdf", "--mode-single", *cfg.bw_args, *mirror,
                          "--layers", layer_arg, "--output", current, cfg.pcb], current)

        if opts.get("rotate_180", False):
            import pdf_tools

            rotated = tmp / f"{stem}_ROTATED.pdf"
            pdf_tools.rotate_pdf_180(current, rotated)
            log("Rotated 180 degrees (applied after mirror)")
            current = rotated

        if final_pdf.exists():
            final_pdf.unlink()
        shutil.copyfile(current, final_pdf)
        log(f"[OK] {final_pdf}")
    finally:
        if cfg.debug:
            log(f"Debug: intermediate files kept in {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------- Gerber names

GERBER_EXT_RE = re.compile(r"^\.(gbr|gtl|gbl|gts|gbs|gto|gbo|gtp|gbp|gko|gm1|g\d+|gp\d+)$", re.IGNORECASE)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _expected_extensions(layers_info):
    ext = {
        "F.Cu": "GTL", "B.Cu": "GBL", "F.Mask": "GTS", "B.Mask": "GBS",
        "F.SilkS": "GTO", "B.SilkS": "GBO", "F.Paste": "GTP", "B.Paste": "GBP",
        "Edge.Cuts": "GKO",
    }
    for canonical, kind, _display in layers_info:
        m = re.match(r"^In(\d+)\.Cu$", canonical)
        if m:
            ext[canonical] = ("GP" if kind.lower() == "power" else "G") + m.group(1)
    return ext


def _aliases(layer):
    aliases = {
        "F.Cu": ["F_Cu", "Top Copper", "TopCopper"],
        "B.Cu": ["B_Cu", "Bottom Copper", "BottomCopper"],
        "F.Mask": ["F_Mask", "Top Solder Mask", "TopMask"],
        "B.Mask": ["B_Mask", "Bottom Solder Mask", "BottomMask"],
        "F.SilkS": ["F_SilkS", "F_Silkscreen", "Top Silkscreen", "TopSilk"],
        "B.SilkS": ["B_SilkS", "B_Silkscreen", "Bottom Silkscreen", "BottomSilk"],
        "F.Paste": ["F_Paste", "Top Paste", "TopPaste"],
        "B.Paste": ["B_Paste", "Bottom Paste", "BottomPaste"],
        "Edge.Cuts": ["Edge_Cuts", "EdgeCuts", "BoardOutline", "Outline"],
    }.get(layer, [])
    m = re.match(r"^In(\d+)\.Cu$", layer)
    if m:
        aliases += [f"In{m.group(1)}_Cu", f"Inner{m.group(1)}"]
    return [layer] + aliases


def job_gerber_ext(cfg):
    """Normalise Gerber file extensions (.GTL, .GBL, .G1...) and copy the outline to .GM1."""
    grb = out_dir(cfg, "01_PCB/GRB")
    layers_info = board_layers(cfg.pcb)
    # Layer user names (e.g. "top_layer") also appear in KiCad's Gerber file names.
    display = {c: d for c, _k, d in layers_info if d}

    def gerbers():
        return [f for f in grb.iterdir() if f.is_file() and GERBER_EXT_RE.match(f.suffix)]

    for layer, ext in sorted(_expected_extensions(layers_info).items()):
        tokens = {_norm(a) for a in _aliases(layer) + ([display[layer]] if layer in display else [])}
        found = None
        for f in gerbers():
            name = f.stem
            # Match on the part after "<project>-" so the project name cannot interfere.
            if name.lower().startswith(cfg.project.lower() + "-"):
                name = name[len(cfg.project) + 1:]
            if _norm(name) in tokens:
                found = f
                break
        if found is None:
            continue
        target = found.with_suffix("." + ext)
        # Only the case differs (KiCad's own .gbl vs .GBL): already right, and on
        # case-insensitive file systems target.exists() would be the file itself.
        if found.suffix.lower() == target.suffix.lower():
            log(f"OK {found.name}")
            continue
        if target.exists():
            target.unlink()
        found.rename(target)
        log(f"Renamed {found.name} -> {target.name}")

    for gko in [f for f in grb.iterdir() if f.suffix.lower() == ".gko"]:
        shutil.copyfile(gko, gko.with_suffix(".GM1"))
        log(f"Copied {gko.name} -> {gko.with_suffix('.GM1').name}")


JOBS = {
    "sch_pdf": job_sch_pdf,
    "pcb_pdf": job_pcb_pdf,
    "implantation": job_implantation,
    "drill_map": job_drill_map,
    "layers": job_layers,
    "gerber_ext": job_gerber_ext,
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in JOBS:
        print("usage: release_jobs.py {" + "|".join(JOBS) + "}", file=sys.stderr)
        return 2
    job = sys.argv[1]
    global _LOG_FILE
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        cfg = Config(HERE / "release_config.json")
        # No log file for gerber_ext: its folder is also zipped for the fab house.
        if os.environ.get("JOBSET_OUTPUT_WORK_PATH") and job != "gerber_ext":
            # KiCad 10 leaves record_output logs empty: write our own next to the outputs.
            _LOG_FILE = open(out_dir(cfg, ".") / f"{job}.log", "w", encoding="utf-8")
        log(f"START {job} ({cfg.project})")
        JOBS[job](cfg)
        log(f"END {job}")
        return 0
    except Exception as e:
        log(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
