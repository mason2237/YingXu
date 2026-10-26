"""Bounded ZIP/direct subtitle preparation, entirely inside disposable directories."""
from pathlib import Path
import stat
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from yingxu.core import ScanCancelled
from yingxu.operations import file_mark, StalePlan
from yingxu.subtitle_sources.imports import prepare_download

SRT = b"1\n00:00:01,000 --> 00:00:02,000\nTest subtitle\n"


class ImportSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def package(self, entries):
        path = self.root / "subtitle.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries:
                archive.writestr(name, content)
        return path

    def prepare(self, path, **kwargs):
        return prepare_download(path, self.root, file_mark(path), **kwargs)

    def test_direct_copy_original_retained_and_repeat_does_not_overwrite(self):
        path = self.root / "中文 & '双语'.srt"
        path.write_bytes(SRT)
        first, _ = self.prepare(path)
        second, _ = self.prepare(path)
        self.assertNotEqual(first[0].path, second[0].path)
        self.assertEqual(path.read_bytes(), SRT)
        self.assertEqual(first[0].path.read_bytes(), SRT)

    def test_nested_zip_and_non_subtitles_are_not_executed(self):
        path = self.package([("字幕/Example.chs.srt", SRT), ("字幕/Example.eng.srt", SRT),
                             ("run.exe", b"MZ"), ("nested.zip", b"PK\x03\x04")])
        files, skipped = self.prepare(path)
        self.assertEqual(len(files), 2)
        self.assertEqual(len(skipped), 2)
        self.assertTrue(all(item.path.read_bytes() == SRT for item in files))

    def test_traversal_absolute_ads_and_reserved_names_reject_entire_package(self):
        for name in ("../escape.srt", "/escape.srt", "C:/escape.srt", "a/../../escape.srt",
                     "a\\..\\escape.srt", "sub.srt:stream", "NUL.srt", "a. /x.srt"):
            with self.subTest(name=name):
                path = self.package([("good.srt", SRT), (name, SRT)])
                with self.assertRaises(ValueError): self.prepare(path)

    def test_duplicate_windows_case_names_rejected(self):
        path = self.package([("Name.srt", SRT), ("NAME.srt", SRT)])
        with self.assertRaises(ValueError): self.prepare(path)

    def test_symlink_and_encryption_rejected(self):
        info = zipfile.ZipInfo("link.srt")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(ValueError): self.prepare(self.package([(info, "target")]))
        path = self.package([("a.srt", SRT)])
        raw = bytearray(path.read_bytes())
        offset = raw.index(b"PK\x01\x02")
        raw[offset+8] |= 1
        path.write_bytes(raw)
        with self.assertRaises(ValueError): self.prepare(path)

    def test_entry_count_ratio_and_expanded_size_limits(self):
        with self.assertRaises(ValueError):
            self.prepare(self.package([(f"{i}.srt", SRT) for i in range(201)]))
        with self.assertRaises(ValueError):
            self.prepare(self.package([("bomb.srt", SRT + b"a"*200000)]))
        path = self.package([("a.srt", SRT), ("b.srt", SRT)])
        with patch("yingxu.subtitle_sources.imports.MAX_EXPANDED_BYTES", len(SRT)):
            with self.assertRaises(ValueError): self.prepare(path)

    def test_invalid_subtitle_is_reported_while_good_subtitle_remains(self):
        files, skipped = self.prepare(self.package([("a.srt", SRT), ("error.srt", b"<html>error</html>")]))
        self.assertEqual(len(files), 1)
        self.assertEqual(len(skipped), 1)

    def test_html_disguised_executable_and_vobsub_not_imported(self):
        for name, content in (("a.srt", b"<html>error</html>"), ("a.srt", b"MZ"+SRT),
                              ("a.sub", b"\x00\x00\x01\xba"+b"binary")):
            path = self.root / name
            path.write_bytes(content)
            with self.assertRaises(ValueError): self.prepare(path)

    def test_rar_7z_corrupt_zip_and_unsupported_compression(self):
        for name in ("a.rar", "a.7z", "a.zip"):
            path = self.root / name
            path.write_bytes(b"invalid")
            with self.assertRaises(ValueError): self.prepare(path)
        path = self.root / "bzip.zip"
        with zipfile.ZipFile(path,"w",zipfile.ZIP_BZIP2) as archive: archive.writestr("a.srt",SRT)
        with self.assertRaises(ValueError): self.prepare(path)

    def test_changed_download_and_outside_root_rejected(self):
        path = self.root / "a.srt"
        path.write_bytes(SRT)
        mark = file_mark(path)
        path.write_bytes(SRT+b"changed")
        with self.assertRaises(StalePlan): prepare_download(path,self.root,mark)
        with self.assertRaises(ValueError): prepare_download(path,self.root/"other",file_mark(path))

    def test_cooperative_cancel_never_returns_partial_import(self):
        path = self.package([("a.srt", SRT)])
        with self.assertRaises(ScanCancelled): self.prepare(path,should_stop=lambda:True)

    def test_shared_batch_budget_counts_invalid_output_too(self):
        path = self.package([("invalid.srt",b"invalid"), ("valid.srt",SRT)])
        budget = {"bytes":len(SRT),"files":10}
        with self.assertRaises(ValueError): self.prepare(path,budget=budget)
        self.assertEqual(budget["bytes"],len(SRT)-len(b"invalid"))
        budget = {"bytes":1024,"files":1}
        with self.assertRaises(ValueError): self.prepare(path,budget=budget)
        self.assertEqual(budget["files"],0)

    @unittest.skipUnless(os.name=='nt','Windows bundled libarchive')
    def test_windows_7z_stream_extracts_without_touching_archive(self):
        source=self.root/'sample[中文].chs.srt';source.write_bytes(SRT)
        path=self.root/'subtitles.7z'
        tar=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/tar.exe'
        subprocess.run([str(tar),'-cf',str(path),'--format=7zip','--',source.name],cwd=self.root,check=True,capture_output=True)
        before=path.read_bytes()
        files,skipped=self.prepare(path)
        self.assertFalse(skipped)
        self.assertEqual(files[0].path.read_bytes(),SRT)
        self.assertEqual(path.read_bytes(),before)


if __name__ == "__main__":
    unittest.main()
