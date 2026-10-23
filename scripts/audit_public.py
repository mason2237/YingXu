"""Read-only checks of publishable files and reachable Git blobs.

Reports locations and categories, never matching secret values. This is a
bounded hygiene check, not a guarantee that arbitrary secrets can be detected.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "provider_key": re.compile(r"\bsk-(?:proj-|ant-api\d+-)?[A-Za-z0-9_-]{24,}\b"),
    "aws_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "credential_assignment": re.compile(r'''(?i)\b(?:api[_-]?key|password|client[_-]?secret|access[_-]?token)\s*[:=]\s*["']([^"'\s]{16,})["']'''),
    "developer_path": re.compile(r'''(?i)(?:[A-Z]:[/\\]+Users[/\\]+(?!Public\b|Default\b)[^/\\\s'"<>]+|D:[/\\]+1[/\\]+2026-\d\d-\d\d[/\\]+ba\b)'''),
}
SECRET_CATEGORIES = set(PATTERNS) - {"developer_path"}


def git(*args, input=None):
    return subprocess.check_output(["git", "-c", "core.quotepath=false", *args], cwd=ROOT, input=input)


def scan(data):
    if b"\0" in data[:8192]:
        return []
    body = data.decode("utf-8", errors="replace")
    hits = []
    for number, line in enumerate(body.splitlines(), 1):
        for category, pattern in PATTERNS.items():
            if pattern.search(line):
                hits.append({"category": category, "line": number})
    return hits


def audit(history=False):
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")
    current = []
    checked = 0
    email_candidates = []
    attribution_email_files = 0
    email = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    for relative in sorted(set(filter(None, paths))):
        source = ROOT / relative
        if not source.is_file() or source.stat().st_size > 5_000_000:
            continue
        checked += 1
        data = source.read_bytes()
        hits = scan(data)
        if b"\0" not in data[:8192]:
            addresses = email.findall(data.decode("utf-8", errors="replace"))
            if addresses and relative.startswith(("licenses/", "frontend/vendor/")):
                attribution_email_files += 1
            elif any(not address.endswith(".invalid") and "example." not in address for address in addresses):
                email_candidates.append(relative)
        if hits:
            current.append({"file": relative, "findings": hits})
    result = {"currentFilesChecked": checked, "current": current, "historyBlobsChecked": 0, "history": [],
              "emailCandidateFiles": email_candidates, "thirdPartyAttributionEmailFiles": attribution_email_files}
    result["commitMetadataFindings"] = scan(git("log", "--all", "--format=%an <%ae>%n%cn <%ce>%n%B"))
    if history:
        objects = git("rev-list", "--objects", "--all").splitlines()
        names = {}
        for item in objects:
            oid, _, name = item.partition(b" ")
            names.setdefault(oid.decode(), name.decode("utf-8", errors="replace"))
        sizes = git("cat-file", "--batch-check", input=("\n".join(names)+"\n").encode()).splitlines()
        blobs = [line.split()[0] for line in sizes if len(line.split()) == 3 and line.split()[1] == b"blob" and int(line.split()[2]) <= 5_000_000]
        data = git("cat-file", "--batch", input=b"\n".join(blobs)+b"\n")
        position = 0
        while position < len(data):
            end = data.index(b"\n", position)
            oid, kind, length = data[position:end].split()
            length = int(length);body = data[end+1:end+1+length];position = end+length+2
            result["historyBlobsChecked"] += 1
            hits = scan(body)
            if hits:
                result["history"].append({"blob": oid.decode(), "file": names[oid.decode()], "findings": hits})
    counts = Counter(hit["category"] for item in current for hit in item["findings"])
    historical = Counter(hit["category"] for item in result["history"] for hit in item["findings"])
    result["summary"] = {"current": dict(counts), "history": dict(historical),
                         "historyRewritten": False, "limits": "Pattern checks; binary media and files over 5 MB excluded; ignored local files are not publication inputs."}
    result["trackedGeneratedFiles"] = [p for p in paths if p.endswith((".spec", ".log", ".pyc", ".env", ".pem", ".p12")) or "/__pycache__/" in p]
    result["sensitiveFilenameCandidates"] = [p for p in paths if Path(p).name.startswith(".env") and Path(p).name != ".env.example"
                                             or p.endswith((".pem", ".key", ".p12", ".pfx"))]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--output", default="work/test-results/public-audit.json")
    args = parser.parse_args()
    report = audit(args.history)
    destination = ROOT / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"files": report["currentFilesChecked"], "blobs": report["historyBlobsChecked"],
                      "summary": report["summary"], "generated": report["trackedGeneratedFiles"],
                      "emailCandidateFiles": report["emailCandidateFiles"],
                      "commitMetadataFindings": report["commitMetadataFindings"],
                      "sensitiveFilenameCandidates": report["sensitiveFilenameCandidates"],
                      "currentLocations": [{"file": item["file"], "lines": [h["line"] for h in item["findings"]]} for item in report["current"]]}, ensure_ascii=False))
    raise SystemExit(any(category in SECRET_CATEGORIES for scope in ("current", "history") for category in report["summary"][scope])
                     or any(item["category"] in SECRET_CATEGORIES for item in report["commitMetadataFindings"]))
