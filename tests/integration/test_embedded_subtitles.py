"""Embedded tracks satisfy requirements without extraction or media mutation."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tests.media_fixtures import mkv, mp4
from yingxu.core import ScanCancelled
from yingxu.embedded_subtitles import assess, track_info, ProbeSession, _BudgetFile, MAX_READ
from yingxu.operations import snapshot_from_review, run_batch
from yingxu.review import ReviewPlan, path_key

ROOT = Path(__file__).resolve().parents[2]


def metadata(*tracks):
    result=[]
    for number,(language,title,forced,codec) in enumerate(tracks,1):
        result.append(track_info(SimpleNamespace(language=language,title=title,forced=forced,
            format=codec,codec_id=None,default='Yes'),number))
    return {"status":"ok","tracks":result}


def decision(info, language='chinese'):
    return assess(info,{"enabled":True,"language":language})


class LanguageRules(unittest.TestCase):
    def test_chinese_passes_and_english_only_does_not(self):
        self.assertTrue(decision(metadata(('zh','简体中文','No','UTF-8')))['satisfied'])
        self.assertFalse(decision(metadata(('en','English','No','UTF-8')))['satisfied'])
        self.assertTrue(decision(metadata(('en','English','No','UTF-8')),'english')['satisfied'])

    def test_bilingual_rule_requires_one_bilingual_track(self):
        both=metadata(('zh','简英双语','No','ASS'))
        separate=metadata(('zh','中文','No','UTF-8'),('en','English','No','UTF-8'))
        self.assertTrue(decision(both,'bilingual')['satisfied'])
        self.assertFalse(decision(separate,'bilingual')['satisfied'])
        self.assertTrue(decision(separate)['satisfied'])
        self.assertTrue(decision(metadata(('zh','中文 / English','No','ASS')),'bilingual')['satisfied'])
        self.assertFalse(decision(metadata(('French','中英双语','No','ASS')),'bilingual')['satisfied'])

    def test_unknown_language_does_not_silently_pass(self):
        info=metadata(('und','Full subtitles','No','UTF-8'))
        self.assertFalse(decision(info)['satisfied'])
        self.assertTrue(decision(info,'any')['satisfied'])

    def test_title_only_bilingual_is_explained(self):
        info=metadata(('und','中英双语','No','ASS'))
        self.assertTrue(decision(info,'bilingual')['satisfied'])
        self.assertEqual(info['tracks'][0]['languageSource'],'title')

    def test_conflicting_language_labels_do_not_pass(self):
        for code in ('eng','French','fr'):
            with self.subTest(code=code):
                self.assertFalse(decision(metadata((code,'简体中文','No','UTF-8')))['satisfied'])

    def test_forced_and_commentary_tracks_are_not_complete_subtitles(self):
        for track in [('zh','Chinese Forced','Yes','UTF-8'),('zh','导演评论','No','ASS')]:
            with self.subTest(track=track):self.assertFalse(decision(metadata(track))['satisfied'])

    def test_chinese_bitmap_subtitles_also_satisfy(self):
        result=decision(metadata(('zho','中文','No','PGS')))
        self.assertTrue(result['satisfied']);self.assertEqual(result['tracks'][0]['kind'],'bitmap')

    def test_script_must_be_known_for_strict_script_rule(self):
        self.assertFalse(decision(metadata(('zh','Chinese','No','ASS')),'simplified')['satisfied'])
        self.assertTrue(decision(metadata(('zh','简英双语','No','ASS')),'simplified')['satisfied'])
        self.assertTrue(decision(metadata(('zh','Traditional Chinese','No','ASS')),'traditional')['satisfied'])

    def test_errors_and_no_tracks_do_not_pass(self):
        for info in ({'status':'ok','tracks':[]},{'status':'error','tracks':[]},{'status':'disabled','tracks':[]}):
            with self.subTest(info=info):self.assertFalse(decision(info)['satisfied'])

    def test_other_preferred_languages(self):
        for code,policy in [('jpn','japanese'),('kor','korean')]:
            self.assertTrue(decision(metadata((code,'','No','UTF-8')),policy)['satisfied'])


class ReviewIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='embedded-review-',dir=ROOT/'work/test-results')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.video=self.root/'电影.mkv';self.video.write_bytes(b'video bytes stay unchanged')
        self.subtitle=self.root/'电影.chs.srt';self.subtitle.write_text('subtitle bytes stay unchanged',encoding='utf-8')
        self.good=decision(metadata(('zh','中文','No','UTF-8')))

    def review(self):return ReviewPlan([self.video],[self.subtitle],embedded={path_key(self.video):self.good})

    def test_existing_embedded_track_means_satisfied_without_external_match(self):
        review=self.review()
        self.assertEqual(review.state(0),'已符合');self.assertFalse(review.rows[0].matches)

    def test_preview_and_execution_do_not_extract_or_touch_files(self):
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        snapshot=snapshot_from_review(self.review())
        self.assertFalse(snapshot.changes);self.assertEqual(snapshot.items[0].action,'unchanged')
        result=run_batch(snapshot)
        self.assertEqual(result.count('unchanged'),1)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})

    def test_satisfied_video_does_not_take_an_external_subtitle_from_other_rows(self):
        (self.root/'other').mkdir();other=self.root/'other/电影.mkv';other.write_bytes(b'another video')
        review=ReviewPlan([self.video,other],[self.subtitle],embedded={path_key(self.video):self.good})
        self.assertFalse(review.rows[0].matches);self.assertEqual(review.rows[1].matches[0].source,self.subtitle)

    def test_manual_override_and_restore_only_change_the_plan(self):
        review=self.review();review.use_embedded(0,False)
        self.assertEqual(review.state(0),'未匹配')
        review.assign(0,self.subtitle);self.assertEqual(review.state(0),'需确认')
        review.use_embedded(0,True)
        self.assertFalse(review.rows[0].matches);self.assertEqual(review.state(0),'已符合')
        self.assertEqual(self.video.read_bytes(),b'video bytes stay unchanged')

    def test_unrelated_download_does_not_replace_satisfied_embedded_track(self):
        review=self.review();cache=self.root/'download.eng.srt';cache.write_bytes(b'download')
        self.assertEqual(review.add_imports([(cache,{'rowIndex':0})]),0)
        self.assertEqual(review.state(0),'已符合');self.assertFalse(review.rows[0].matches)


class ActualContainerReader(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='embedded-container-',dir=ROOT/'work/test-results')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_real_mkv_and_mp4_metadata_via_reused_helper(self):
        chinese=mkv(self.root/'中文 空格 & 视频.mkv',[('zho','简体中文',False)])
        english=mp4(self.root/'english.mp4','eng')
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        with ProbeSession() as reader:
            zh=reader.probe(chinese);pid=reader.process.pid
            en=reader.probe(english);self.assertEqual(reader.process.pid,pid)
        self.assertTrue(decision(zh)['satisfied']);self.assertFalse(decision(en)['satisfied'])
        self.assertTrue(decision(en,'english')['satisfied'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})

    def test_invalid_video_and_unknown_language_are_not_accepted(self):
        invalid=self.root/'invalid.mkv';invalid.write_bytes(b'not a video')
        unknown=mkv(self.root/'unknown.mkv',[('und','Full',False)])
        with ProbeSession() as reader:
            self.assertFalse(decision(reader.probe(invalid))['satisfied'])
            self.assertFalse(decision(reader.probe(unknown))['satisfied'])

    def test_cancel_before_start_does_not_spawn_helper(self):
        with ProbeSession(lambda:True) as reader:
            with self.assertRaises(ScanCancelled):reader.probe(self.root/'unused.mkv')
            self.assertIsNone(reader.process)

    def test_read_budget_is_bounded(self):
        reader=_BudgetFile(BytesIO(b'anything'))
        with self.assertRaises(ValueError):reader.read(MAX_READ+1)
        reader.deadline=-1
        with self.assertRaises(ValueError):reader.read(1)


if __name__=='__main__':unittest.main()
