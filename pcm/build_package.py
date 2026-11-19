"""Build the KiCad Plugin and Content Manager (PCM) package.

    python pcm/build_package.py 0.0.2

Writes to dist/:
- <identifier>-<version>.zip        the package (attach it to the GitHub release)
- metadata.json                     the file to submit to gitlab.com/kicad/addons/metadata
                                    (packages/<identifier>/metadata.json), with download_*
- icon.png                          the 64x64 icon to submit next to it

The archive is reproducible: sorted entries, fixed timestamps and LF line endings, so the
same sources give the same SHA-256 on Windows, macOS, Linux and in CI.
"""

import argparse
import copy
import hashlib
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "pcm" / "metadata.json"
REPO_URL = "https://github.com/kevinwysocki/kicad_release_wizard"

# Archive path -> source path. Everything under plugins/ is installed as the plugin folder.
PLUGIN_FILES = [
    "__init__.py",
    "action_release_wizard.py",
    "release_wizard_dialog.py",
    "board_outline.py",
    "bom_fields.py",
    "i18n.py",
    "platform_tools.py",
    "requirements.txt",
    "LICENSE",
    "resources/logo.png",
]
PLUGIN_GLOBS = ["job_scripts/*.py"]
ICON = "resources/icon_64.png"

TEXT_SUFFIXES = {".py", ".json", ".txt", ".md", ""}
FIXED_DATE = (2020, 1, 1, 0, 0, 0)

# Rules of https://go.kicad.org/pcm/schemas/v1 and of the KiCad addons guide.
IDENTIFIER_RE = re.compile(r"^[a-zA-Z][-a-zA-Z0-9.]{0,98}[a-zA-Z0-9]$")
VERSION_RE = re.compile(r"^\d{1,4}(\.\d{1,4}(\.\d{1,6})?)?$")
KICAD_VERSION_RE = re.compile(r"^\d{1,2}(\.\d{1,2}(\.\d{1,2})?)?$")
STATUSES = {"stable", "testing", "development", "deprecated"}


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def validate(meta):
    for key in ("name", "description", "description_full", "identifier", "type",
                "author", "license", "resources", "versions"):
        if key not in meta:
            fail(f"metadata.json: missing '{key}'")
    if not IDENTIFIER_RE.match(meta["identifier"]):
        fail(f"invalid identifier: {meta['identifier']}")
    if len(meta["description"]) > 150:
        fail(f"description is {len(meta['description'])} characters (150 max)")
    if len(meta["description_full"]) > 5000:
        fail("description_full exceeds 5000 characters")
    if not meta["author"].get("contact"):
        fail("author.contact is required")
    for v in meta["versions"]:
        if not VERSION_RE.match(v.get("version", "")):
            fail(f"invalid version: {v.get('version')}")
        if v.get("status") not in STATUSES:
            fail(f"invalid status: {v.get('status')}")
        for key in ("kicad_version", "kicad_version_max"):
            if key in v and not KICAD_VERSION_RE.match(v[key]):
                fail(f"invalid {key}: {v[key]}")


def read_source(path):
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return data


def add(zf, arcname, data):
    info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version", help="package version, e.g. 0.0.2 (a leading 'v' is accepted)")
    ap.add_argument("--out", default=str(ROOT / "dist"), help="output folder (default: dist/)")
    args = ap.parse_args()
    version = args.version.lstrip("vV")

    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    entry = dict(template["versions"][0], version=version)

    # metadata.json inside the archive: no download_* keys (they depend on the archive).
    packaged = copy.deepcopy(template)
    packaged["versions"] = [entry]
    validate(packaged)

    entries = {}
    for rel in PLUGIN_FILES:
        entries["plugins/" + rel] = ROOT / rel
    for pattern in PLUGIN_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            entries["plugins/" + path.relative_to(ROOT).as_posix()] = path
    entries["resources/icon.png"] = ROOT / ICON
    for arcname, path in entries.items():
        if not path.is_file():
            fail(f"missing file: {path}")

    buf = io.BytesIO()
    install_size = 0
    with zipfile.ZipFile(buf, "w") as zf:
        for arcname in sorted(entries):
            data = read_source(entries[arcname])
            install_size += len(data)
            add(zf, arcname, data)
        meta_bytes = (json.dumps(packaged, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        install_size += len(meta_bytes)
        add(zf, "metadata.json", meta_bytes)
    archive = buf.getvalue()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    zip_name = f"{template['identifier']}-{version}.zip"
    (out / zip_name).write_bytes(archive)
    shutil.copyfile(ROOT / ICON, out / "icon.png")

    # metadata.json to submit to the KiCad metadata repository.
    submitted = copy.deepcopy(template)
    submitted["versions"] = [dict(
        entry,
        download_url=f"{REPO_URL}/releases/download/{args.version}/{zip_name}",
        download_sha256=hashlib.sha256(archive).hexdigest(),
        download_size=len(archive),
        install_size=install_size,
    )]
    (out / "metadata.json").write_text(
        json.dumps(submitted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    print(f"package : {out / zip_name} ({len(archive)} bytes, {len(entries) + 1} files)")
    print(f"sha256  : {submitted['versions'][0]['download_sha256']}")
    print(f"url     : {submitted['versions'][0]['download_url']}")
    print(f"metadata: {out / 'metadata.json'}")


if __name__ == "__main__":
    main()
