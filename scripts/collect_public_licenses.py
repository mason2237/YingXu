"""Fetch license documents only, from reviewed primary publisher URLs.

No downloaded script is executed. Normal application/build startup is offline.
"""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor
from urllib.error import URLError, HTTPError
import time

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "licenses"
DOCUMENTS = {
    "PolyForm-Noncommercial-1.0.0.txt": "https://polyformproject.org/licenses/noncommercial/1.0.0.txt",
    "LGPL-3.0-only.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/LGPL-3.0-only.txt",
    "GPL-3.0-only.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/GPL-3.0-only.txt",
    "LGPL-2.1-only.txt": "https://raw.githubusercontent.com/spdx/license-list-data/main/text/LGPL-2.1-only.txt",
    "GPL-2.0-only.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/GPL-2.0-only.txt",
    "Apache-2.0.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/Apache-2.0.txt",
    "GFDL-1.3-no-invariants-only.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/GFDL-1.3-no-invariants-only.txt",
}
INDEXES = {
    "QtCore": "https://doc.qt.io/qt-6.12/qtcore-index.html",
    "QtGui": "https://doc.qt.io/qt-6.12/qtgui-index.html",
    "QtNetwork": "https://doc.qt.io/qt-6.12/qtnetwork-index.html",
    "QtWidgets": "https://doc.qt.io/qt-6.12/qtwidgets-index.html",
    "QtQml": "https://doc.qt.io/qt-6.12/qtqml-index.html",
    "QtQuick": "https://doc.qt.io/qt-6.12/qtquick-index.html",
    "QtSvg": "https://doc.qt.io/qt-6.12/qtsvg-index.html",
    "QtPositioning": "https://doc.qt.io/qt-6.12/qtpositioning-index.html",
    "QtWebChannel": "https://doc.qt.io/qt-6.12/qtwebchannel-index.html",
    "QtWebEngine": "https://doc-snapshots.qt.io/qtwebengine/qtwebengine-licensing.html",
}


def download(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "YingXu-license-inventory/1.0"}), timeout=25) as response:
                data = response.read(8_000_001)
                if len(data) > 8_000_000:
                    raise ValueError("License document exceeds the bounded download size")
                return data, response.url
        except HTTPError as error:
            if error.code < 500 or attempt == 2:raise
        except (URLError, OSError):
            if attempt == 2:raise
        time.sleep(1 + attempt)


class Document(HTMLParser):
    def __init__(self):
        super().__init__();self.links = [];self.text = [];self.active = 0;self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in {"script", "style"}:self.skip += 1
        if tag in {"main", "article"} or (tag == "div" and ("descr" in attrs.get("class", "").split() or attrs.get("id") == "mainContent")):
            self.active += 1
        if self.active and tag in {"p", "br", "pre", "h1", "h2", "h3", "li"}:self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:self.skip -= 1
        # Keep the content after entering the article; navigation/footer is
        # harmless attribution, while nested divs must not truncate a license.
        if self.active and tag in {"p", "pre", "li"}:self.text.append("\n")

    def handle_data(self, data):
        if self.active and not self.skip:self.text.append(data)


def main():
    DESTINATION.mkdir(exist_ok=True)
    entries = []
    for name, url in DOCUMENTS.items():
        data, resolved = download(url)
        if b"<html" in data[:500].lower() or len(data) < 1000:
            raise ValueError(f"Not the expected plain license text: {url}")
        (DESTINATION / name).write_bytes(data)
        if name.startswith("PolyForm"):
            (ROOT / "LICENSE").write_bytes(data)  # Exact official bytes, no header or edits.
        entries.append({"file": name, "url": url, "resolvedURL": resolved, "sha256": hashlib.sha256(data).hexdigest(), "mode": "verbatim"})
    urls = set()
    for module, url in INDEXES.items():
        try:
            data, resolved = download(url)
        except Exception as error:
            print(f"INDEX {module}: {type(error).__name__}", flush=True)
            continue
        document = Document();document.feed(data.decode("utf-8"))
        found = {urljoin(resolved, link).split("#")[0] for link in document.links
                 if "-attribution-" in link or "-3rdparty-" in link or "chromium-licensing" in link}
        urls.update(link for link in found if urlparse(link).hostname in {"doc.qt.io", "doc-snapshots.qt.io"})
        print(f"INDEX {module}: {len(found)} notice pages", flush=True)
    if len(urls) > 180:
        raise ValueError("Unexpectedly broad notice crawl; review indexes before proceeding")

    def collect(url):
        data, resolved = download(url)
        document = Document();document.feed(data.decode("utf-8"))
        text = "".join(document.text).strip()
        if len(text) < 100:
            raise ValueError(f"Notice text missing: {url}")
        name = Path(urlparse(url).path).stem + ".txt"
        output = ("Source: " + resolved + "\n\n" + text + "\n").encode("utf-8")
        (DESTINATION / name).write_bytes(output)
        return {"file": name, "url": url, "resolvedURL": resolved, "sha256": hashlib.sha256(output).hexdigest(), "mode": "publisher-page text; license wording retained"}

    with ThreadPoolExecutor(max_workers=5) as executor:
        entries.extend(executor.map(collect, sorted(urls)))
    (DESTINATION / "SOURCES.json").write_text(json.dumps({"documents": entries, "indexes": INDEXES}, indent=2), encoding="utf-8")
    print(f"Saved {len(entries)} primary-source documents; LICENSE is byte-identical to official PolyForm text.", flush=True)


if __name__ == "__main__":
    main()
