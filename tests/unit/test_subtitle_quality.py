"""Subtitle diagnosis is bounded, source-located, format-aware and read-only."""
import unittest

from yingxu.domain.subtitle_document import MAX_CUES,MAX_ISSUES,SubtitleRead,parse_document
from yingxu.domain.subtitle_quality import analyze,inspect_document
from yingxu.domain.matching import ScanCancelled


def check(text,format='srt',**options):
    return analyze(SubtitleRead(format,text,'utf-8','sample'),**options)


class SubtitleQualityTests(unittest.TestCase):
    def test_clean_srt_and_invalid_timestamps_are_distinct(self):
        clean=check('1\n00:00:01,000 --> 00:00:02,000\nHello\n')
        self.assertEqual(clean.status,'clean');self.assertEqual(clean.summary()['cueCount'],1)
        for time,code in (('00:00:02,000 --> 00:00:01,000','REVERSED_TIME'),
                          ('00:xx:02,000 --> 00:00:03,000','INVALID_TIME'),
                          ('00:00:01,000 --> 00:00:01,000','ZERO_DURATION')):
            with self.subTest(time=time):
                report=check(f'42\n{time}\nText\n')
                issue=next(i for i in report.document.issues if i.code==code)
                self.assertEqual((issue.line,issue.cue,issue.excerpt),(2,'42','Text'))
                self.assertNotEqual(report.status,'clean')

    def test_empty_ass_is_error_and_legitimate_layers_are_only_info(self):
        self.assertGreater(check('[Script Info]\n[Events]\n','ass').summary()['errors'],0)
        text='[Script Info]\nTitle: Generated\n[V4+ Styles]\nFormat: Name, Fontname\nStyle: Default,Arial\n[Events]\nFormat: Layer, Start, End, Style, Text\nDialogue: 0,0:00:01.00,0:00:03.00,Default,中文, with comma\nDialogue: 1,0:00:01.00,0:00:03.00,Default,English\nComment: 0,0:00:00.00,0:00:01.00,Default,Preserve comment\n'
        report=check(text,'ass')
        self.assertEqual(report.summary()['errors'],0)
        self.assertEqual(report.document.cues[0].text,'中文, with comma')
        self.assertEqual(report.document.cues[1].layer,'1')
        self.assertEqual(report.document.cues[2].kind,'comment')
        self.assertTrue(any(i.code=='OVERLAP' and i.severity=='info' for i in report.document.issues))
        self.assertTrue(any(b.raw.startswith('Style:') for b in report.document.blocks))

    def test_ass_format_order_and_ssa_fields_are_respected(self):
        document=parse_document('[Events]\nFormat: Start, Text, End, Style, Marked\nDialogue: 0:00:01.00,Text, contains, commas,0:00:02.00,Main,Marked=0\n','ssa')
        cue=document.cues[0]
        self.assertEqual(cue.text,'Text, contains, commas');self.assertEqual(cue.style,'Main')
        self.assertEqual(cue.layer,'Marked=0');self.assertEqual(cue.start,1000)
        self.assertIn('Text, contains, commas',cue.raw)

    def test_vtt_preserves_non_cue_blocks_identifier_and_settings(self):
        text='WEBVTT\nKind: captions\n\nNOTE Generated note\nnot a cue\n\nSTYLE\n::cue { color: white; }\n\nREGION\nid:main\n\nscene-one\n00:01.000 --> 00:03.500 align:start position:20%\n<v Alice>Hello</v>\n'
        report=check(text,'vtt')
        self.assertEqual(report.summary()['errors'],0)
        cue=report.document.cues[0]
        self.assertEqual((cue.identifier,cue.start,cue.end),('scene-one',1000,3500))
        self.assertEqual(cue.settings,'align:start position:20%')
        self.assertEqual({b.kind for b in report.document.blocks},{'header','NOTE','STYLE','REGION'})

    def test_order_duplicates_empty_encoding_and_reading_speed_are_warnings(self):
        text='1\n00:00:03,000 --> 00:00:04,000\nFranÃ§ais cafÃ©\n\n2\n00:00:01,000 --> 00:00:02,000\n\n3\n00:00:03,000 --> 00:00:04,000\nFranÃ§ais cafÃ©\n'
        report=check(text,max_cps=5)
        codes={i.code for i in report.document.issues}
        self.assertTrue({'SUSPECT_ENCODING','OUT_OF_ORDER','EMPTY_TEXT','DUPLICATE','READING_SPEED'}<=codes)
        with self.assertRaises(ValueError):check(text,max_cps=float('nan'))

    def test_issue_and_cue_limits_are_never_silently_clean(self):
        bad='\n'.join(f'{i}\n00:xx:00,000 --> 00:00:01,000\nText\n' for i in range(600))
        report=check(bad)
        self.assertEqual(len(report.document.issues),MAX_ISSUES);self.assertFalse(report.document.complete)
        good='\n'.join(f'{i}\n{i//3600:02}:{i//60%60:02}:{i%60:02},000 --> {i//3600:02}:{i//60%60:02}:{i%60:02},500\nX\n' for i in range(MAX_CUES+1))
        document=parse_document(good,'srt')
        self.assertEqual(len(document.cues),MAX_CUES);self.assertFalse(document.complete)
        self.assertFalse(check('x'*40000).document.complete)

    def test_cancellation_and_bitmap_limit_are_explicit(self):
        with self.assertRaises(ScanCancelled):check('Generated',should_stop=lambda:True)
        self.assertEqual(check('',format='sup').status,'unsupported')

    def test_missing_separator_is_reported_instead_of_silently_clean(self):
        report=check('1\n00:00:01,000 --> 00:00:03,000\nText\n2\n00:00:04,000 --> 00:00:05,000\nNext\n')
        issue=next(i for i in report.document.issues if i.code=='MISSING_SEPARATOR')
        self.assertEqual(issue.line,5);self.assertEqual(issue.severity,'warning')
        self.assertNotEqual(report.status,'clean')


if __name__=='__main__':unittest.main()
