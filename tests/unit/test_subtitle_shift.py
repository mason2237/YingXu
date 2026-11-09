import unittest
from yingxu.domain.sync_models import transform


class SubtitleShiftTests(unittest.TestCase):
    def test_srt_vtt_cross_hour_and_negative_refusal(self):
        for format,text in [('srt','1\r\n00:59:59,000 --> 01:00:00,000\r\nText\r\n'),
                            ('vtt','WEBVTT\n\nNOTE keep this\n\ncue\n59:59.000 --> 01:00:00.000 position:20%\nText\n')]:
            result=transform(text,format,2000)
            self.assertIn('01:00:01',result);self.assertIn('Text',result)
            if format=='vtt':self.assertIn('position:20%',result);self.assertIn('NOTE keep this',result)
        with self.assertRaisesRegex(ValueError,'负时间'):transform('1\n00:00:01,000 --> 00:00:02,000\nText\n','srt',-3000)

    def test_ass_styles_comments_layers_and_commas_preserved(self):
        text='[Script Info]\nTitle: keep\n[Events]\nFormat: Layer, Start, End, Style, Text\nDialogue: 2,0:00:01.00,0:00:03.00,Fancy,{\\i1}Text,with,commas\nComment: 1,0:00:01.00,0:00:02.00,Fancy,comment\n'
        for format in ('ass','ssa'):
            result=transform(text,format,1000);self.assertIn('0:00:02.00',result);self.assertIn('{\\i1}Text,with,commas',result);self.assertIn('Comment: 1,',result)
