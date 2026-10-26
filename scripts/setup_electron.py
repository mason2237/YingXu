"""Download the pinned official Electron runtime; never run package install scripts."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "45.0.0"
ELECTRON_SHA256 = "ae53887a23bb640369c93dbd38c408a2af5c0deb86f2fa76c6c244cb444b7f47"
TOOLS = ROOT / "work" / "tools"


def fetch(url, path):
    with urlopen(Request(url, headers={"User-Agent": "YingXu-architecture-prototype"}), timeout=90) as source:
        with path.open("wb") as target:
            while block := source.read(1024 * 1024):
                target.write(block)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--presentmon', action='store_true')
    args = parser.parse_args()
    TOOLS.mkdir(parents=True, exist_ok=True)
    if args.presentmon:
        filename = 'PresentMon-2.6.0-x64.exe'
        target = TOOLS / filename
        fetch(f'https://github.com/GameTechDev/PresentMon/releases/download/v2.6.0/{filename}', target)
        with target.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != 'b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af':
            raise RuntimeError('PresentMon checksum mismatch')
        print(json.dumps({'tool': filename, 'sha256': actual, 'installed': False}))
        return 0
    name = f"electron-v{VERSION}-win32-x64.zip"
    base = f"https://github.com/electron/electron/releases/download/v{VERSION}"
    sums = TOOLS / f"electron-{VERSION}-SHASUMS256.txt"
    fetch(f"{base}/SHASUMS256.txt", sums)
    expected = next(line.split()[0] for line in sums.read_text().splitlines() if line.split()[-1].lstrip('*') == name)
    if expected != ELECTRON_SHA256:
        raise RuntimeError('Official checksum differs from the reviewed runtime pin')
    archive = TOOLS / name
    previous = None
    if archive.exists():
        with archive.open("rb") as stream:
            previous = hashlib.file_digest(stream, "sha256").hexdigest()
    if previous != expected:
        fetch(f"{base}/{name}", archive)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise RuntimeError("Electron archive checksum mismatch")
    destination = TOOLS / f"electron-{VERSION}"
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            resolved = (destination / member.filename).resolve()
            if not resolved.is_relative_to(destination.resolve()):
                raise RuntimeError("Unexpected archive path")
        source.extractall(destination)
    result = {"version": VERSION, "source": f"{base}/{name}", "sha256": actual,
              "officialChecksums": f"{base}/SHASUMS256.txt", "installScriptsExecuted": False}
    (TOOLS / "electron-runtime.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
