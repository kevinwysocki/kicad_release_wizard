"""Locate kicad-cli and a Python 3 interpreter on Windows, macOS and Linux."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# Hide console windows of helper processes on Windows.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0


def _exe(name):
    return name + ".exe" if IS_WINDOWS else name


def _kicad_dirs():
    """Folders that may hold KiCad's binaries, derived from the running interpreter."""
    exe = Path(sys.executable).resolve()
    dirs = [exe.parent]
    for parent in exe.parents:
        if parent.suffix == ".app":  # macOS bundle: KiCad.app/Contents/MacOS
            dirs.append(parent / "Contents" / "MacOS")
            break
    return dirs


def find_kicad_cli():
    """kicad-cli of the running KiCad first, then PATH and the usual install folders."""
    candidates = []
    if os.environ.get("KICAD_CLI"):
        candidates.append(Path(os.environ["KICAD_CLI"]))
    candidates += [d / _exe("kicad-cli") for d in _kicad_dirs()]
    which = shutil.which("kicad-cli")
    if which:
        candidates.append(Path(which))
    if IS_WINDOWS:
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "KiCad"
        candidates.append(pf / "10.0" / "bin" / "kicad-cli.exe")
    elif IS_MAC:
        candidates.append(Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"))
    else:
        candidates += [Path("/usr/bin/kicad-cli"), Path("/usr/local/bin/kicad-cli")]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def _probe(cmd):
    """Return (executable, has_pymupdf) for a Python command, or None."""
    code = (
        "import sys\n"
        "try:\n import fitz; ok = True\n"
        "except Exception:\n ok = False\n"
        "print(sys.version_info[0]); print(int(ok)); print(sys.executable)"
    )
    try:
        res = subprocess.run(
            cmd + ["-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
            creationflags=NO_WINDOW,
        )
    except Exception:
        return None
    lines = (res.stdout or "").strip().splitlines()
    if res.returncode != 0 or len(lines) < 3 or lines[0] != "3":
        return None
    return lines[2].strip(), lines[1] == "1"


def find_python():
    """Return (python executable, has_pymupdf) for the job scripts, or (None, False).

    The system Python 3 is preferred (PyMuPDF is installed there with pip); one with
    PyMuPDF wins. KICAD_RELEASE_WIZARD_PYTHON overrides the search.
    """
    forced = os.environ.get("KICAD_RELEASE_WIZARD_PYTHON")
    if forced:
        found = _probe([forced])
        return found if found else (None, False)

    commands = [["py", "-3"], ["python"], ["python3"]] if IS_WINDOWS else [["python3"], ["python"]]
    # KiCad's bundled interpreter as a last resort (no PyMuPDF, but enough for most jobs).
    commands += [[str(d / _exe(n))] for d in _kicad_dirs() for n in ("python3", "python")]

    first = None
    seen = set()
    for cmd in commands:
        if len(cmd) == 1 and os.sep in cmd[0] and not Path(cmd[0]).is_file():
            continue
        found = _probe(cmd)
        if not found or found[0].lower() in seen:
            continue
        seen.add(found[0].lower())
        if found[1]:
            return found
        first = first or found
    return first if first else (None, False)


def command_path(path):
    """A path usable in a jobset command, which may not contain quotes.

    KiCad runs special_execute commands through cmd.exe on Windows with escaped
    quotes, so paths must not contain spaces: use the 8.3 short name there.
    """
    path = str(path)
    if " " not in path:
        return path
    if IS_WINDOWS:
        import ctypes

        buf = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.GetShortPathNameW(path, buf, len(buf)) and " " not in buf.value:
            return buf.value
    raise RuntimeError(f"Path with spaces cannot be used in a jobset command: {path}")
