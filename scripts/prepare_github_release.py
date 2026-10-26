"""Prepare local GitHub assets from the saved source commit; never upload.

The source export omits .git and ignored local data while retaining the
original repository and its full history on disk.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yingxu.version import VERSION
from scripts.audit_public import audit


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    # Never export unsaved code under an unrelated source revision.
    if git("status", "--porcelain").strip():
        raise RuntimeError("Save and commit project changes before exporting the public source")
    hygiene = audit()
    if hygiene["current"] or hygiene["sensitiveFilenameCandidates"] or hygiene["trackedGeneratedFiles"] or hygiene["emailCandidateFiles"]:
        raise RuntimeError("Review current public-file hygiene findings before exporting")
    commit = git("rev-parse", "HEAD").decode().strip()
    built = ROOT / "outputs" / "releases" / VERSION
    package = built / f"YingXu-{VERSION}-windows-x64.zip"
    manifest = json.loads((built / "YingXu/BUILD_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest["version"] != VERSION or manifest["applicationLicense"] != "PolyForm-Noncommercial-1.0.0":
        raise RuntimeError("Build version/license does not match the source")
    runtime_sources = {**manifest["pythonSources"], **manifest.get('desktopSources', {}),
                       **{f"frontend{key}": value for key, value in manifest["frontend"].items()}}
    for relative, expected in runtime_sources.items():
        if sha(ROOT / relative) != expected:
            raise RuntimeError("Binary was built from different sources: " + relative)
    output = ROOT / "outputs" / "github-release" / VERSION
    output.mkdir(parents=True, exist_ok=True)
    source = output / f"YingXu-{VERSION}-source.zip"
    subprocess.run(["git", "archive", "--format=zip", f"--prefix=YingXu-{VERSION}-source/",
                    "-o", str(source), commit], cwd=ROOT, check=True)
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        if any("/.git/" in item or "/.venv" in item or "/work/test-results/" in item or item.endswith((".spec", ".pyc", ".log")) for item in names):
            raise RuntimeError("Local/generated files leaked into source export")
        if not any(item.endswith("/LICENSE") for item in names):
            raise RuntimeError("Source export missing project license")
        # git archive honors core.autocrlf. Verify actual saved code, accepting
        # only LF/CRLF conversion for known UTF-8 source formats, never binary edits.
        line_endings = 0
        for relative in runtime_sources:
            saved = archive.read(f"YingXu-{VERSION}-source/{relative}")
            current = (ROOT / relative).read_bytes()
            if saved == current:continue
            if Path(relative).suffix not in {'.py','.js','.cjs','.json','.css','.html','.svg'} or saved.replace(b'\r\n',b'\n') != current.replace(b'\r\n',b'\n'):
                raise RuntimeError('Exported runtime source differs: ' + relative)
            line_endings += 1
    shutil.copy2(package, output / package.name)
    shutil.copy2(ROOT / "release/RELEASE_NOTES.md", output)
    files = [output / package.name, source]
    (output / "SHA256SUMS.txt").write_text("".join(f"{sha(path)}  {path.name}\n" for path in files), encoding="utf-8")
    result = {"version": VERSION, "sourceCommit": commit, "applicationLicense": "PolyForm-Noncommercial-1.0.0",
              "runtimeSourceFilesVerified": len(runtime_sources), "lfCrLfOnlyDifferences": line_endings,
              "cleanWindowsTested": False, "gitHistoryIncluded": False, "uploaded": False,
              "files": [{"name": path.name, "bytes": path.stat().st_size, "sha256": sha(path)} for path in files]}
    (output / "RELEASE_MANIFEST.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
