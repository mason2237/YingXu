"""Offline checks of online-discovery boundaries, using synthetic files only."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from yingxu.subtitle_sources import downloads
from yingxu.subtitle_sources.zimuku import public_https, source_url, search_terms, submit_search_script
from yingxu.subtitle_sources.websites import WEBSITES, website_for

ROOT = Path(__file__).resolve().parents[2]


class SearchTests(unittest.TestCase):
    def test_basename_only_and_release_tags(self):
        cases = {
            r"C:\private\Example.Show.S01E02.1080p.WEB-DL.mkv": "Example Show",
            "电影.2024.2160p.BluRay.mp4": "电影",
            "1917.2019.1080p.mkv": "1917",
            "剧集.第12集.H264.mp4": "剧集",
            '[YTS] Interstellar.2014.2160p.BluRay.x265.mkv':'Interstellar',
            '星际穿越.Interstellar.2014.2160p.mkv':'星际穿越',
            '[The.Matrix].1999.1080p.mkv':'The Matrix',
            '狂飙S01E03.1080p.mkv':'狂飙',
            '进击的巨人.第一季.第02集.mkv':'进击的巨人',
            '[DBD-Raws][命运石之门][01][1080p].mkv':'命运石之门',
        }
        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                self.assertEqual(search_terms(filename), expected)

    def test_host_and_protocol_restrictions(self):
        self.assertTrue(source_url("https://zimuku.org/"))
        self.assertTrue(source_url("https://www.zimuku.org:443/"))
        self.assertTrue(public_https("https://cdn.example.com/subtitle.zip"))
        self.assertFalse(source_url("https://zimuku.org.example.com/"))
        for url in ("file:///C:/private", "http://zimuku.org/", "yingxu://app/workspace.html",
                    "https://localhost/", "https://127.0.0.1/", "https://[::1]/", "https://10.0.0.1/",
                    "https://user:example.fixture@zimuku.org/", "https://zimuku.org:8443/", "https://[invalid"):
            with self.subTest(url=url):
                self.assertFalse(public_https(url))

    def test_search_query_is_a_json_value(self):
        query = "中文 \";alert(1)//\n"
        script = submit_search_script(query)
        self.assertIn(json.dumps(query, ensure_ascii=True), script)
        self.assertIn("candidates.length !== 1", script)
        self.assertIn("allowed(form.action", script)
        self.assertNotIn("/search?q=", script)

    def test_site_switching_keeps_provider_boundaries(self):
        self.assertEqual(len(WEBSITES), 4)
        for site in WEBSITES:
            self.assertTrue(source_url(site.home, site.hosts))
        self.assertTrue(source_url("https://srtku.com/", website_for("zimuku").hosts))
        self.assertFalse(source_url("https://subhd.me/", website_for("zimuku").hosts))
        self.assertFalse(source_url("https://zimuku.org/", website_for("subhd").hosts))
        with self.assertRaises(ValueError):
            website_for("https://untrusted.example/")


class DownloadTests(unittest.TestCase):
    def test_same_origin_blob_subtitles_only(self):
        site = website_for('subhd')
        token = 'c0c59b32-e322-416c-8872-4c0dc65dca87'
        self.assertTrue(downloads.same_origin_blob('blob:https://subhd.me/'+token,
                        'https://subhd.me/down/example',site.hosts))
        self.assertTrue(downloads.same_origin_blob('blob:https://subhd.me:443/'+token,
                        'https://subhd.me/a/example',site.hosts))
        for url in ('data:text/plain,test', 'blob:null/'+token, 'blob:http://subhd.me/'+token,
                    'blob:https://subhd.one/'+token,'blob:https://subhd.me.example.com/'+token,
                    'blob:https://localhost/'+token,'blob:https://subhd.me/not-a-uuid',
                    'blob:https://subhd.me/'+token+'?extra=1','blob:https://subhd.me/'+token+'#fragment',
                    'blob:https://subhd.me:8443/'+token,'blob:https://subhd.me/../'+token):
            with self.subTest(url=url):
                self.assertFalse(downloads.same_origin_blob(url,'https://subhd.me/down/example',site.hosts))
        self.assertFalse(downloads.same_origin_blob('blob:https://subhd.me/'+token,
                         'https://other.example.com/',site.hosts))

    def setUp(self):
        base = ROOT / "work/test-results"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="source-test-", dir=base)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def file(self, name, data):
        path = downloads.reserve_download(self.root, name)
        path.write_bytes(data)
        return path

    def test_filename_limits_and_reserved_names(self):
        self.assertEqual(downloads.safe_filename(r"..\..\字幕.srt"), "字幕.srt")
        self.assertEqual(downloads.safe_filename("NUL.srt"), "_NUL.srt")
        self.assertEqual(downloads.safe_filename("COM1.ass"), "_COM1.ass")
        self.assertNotIn(":", downloads.safe_filename("name:stream.srt"))
        for name in ("subtitle.exe", "archive.zip.exe", "file.cmd", "file.srt:stream"):
            with self.assertRaises(ValueError):
                downloads.safe_filename(name)

    def test_unique_staging_and_exclusive_receipt(self):
        first = self.file("same.srt", b"one")
        second = self.file("same.srt", b"two")
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), b"one")
        self.assertEqual(second.read_bytes(), b"two")
        downloads.write_receipt(first, {"status": "pending", "matchConfirmed": False})
        with self.assertRaises(FileExistsError):
            downloads.write_receipt(first, {"status": "overwrite"})

    def test_subtitle_formats_and_encodings(self):
        srt = "1\n00:00:01,000 --> 00:00:02,000\n字幕\n"
        for encoding in ("utf-8-sig", "utf-16", "gb18030"):
            with self.subTest(encoding=encoding):
                self.assertEqual(downloads.inspect_download(self.file("subtitle.srt", srt.encode(encoding))),
                                 "subtitle_candidate")
        for name, data in (("s.ass", b"[Script Info]\n[Events]\nDialogue: test"),
                           ("s.vtt", b"WEBVTT\n\n00:01.000 --> 00:02.000\ntext"),
                           ("s.sub", b"{1}{20}text"), ("s.sup", b"PGsample")):
            self.assertEqual(downloads.inspect_download(self.file(name, data)), "subtitle_candidate")

    def test_error_pages_programs_and_empty_files_are_rejected(self):
        for data in (b"", b"<!DOCTYPE html><html>Verify</html>", b"MZbinary", b"not a subtitle"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                downloads.inspect_download(self.file("s.srt", data))

    def test_archives_are_only_staged(self):
        for name, data in (("s.zip", b"PK\x03\x04fake"), ("s.rar", b"Rar!\x1a\x07fake"),
                           ("s.7z", b"7z\xbc\xaf\x27\x1cfake")):
            self.assertEqual(downloads.inspect_download(self.file(name, data)), "archive_pending")
        with self.assertRaises(ValueError):
            downloads.inspect_download(self.file("s.zip", b"<html>error</html>"))

    def test_size_is_checked_before_reading_content(self):
        path = self.file("s.srt", b"12345")
        with patch.object(downloads, "MAX_DOWNLOAD_BYTES", 4), self.assertRaises(ValueError):
            downloads.inspect_download(path)


if __name__ == "__main__":
    unittest.main()
