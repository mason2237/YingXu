"""Optional parser output cannot silently become matching authority."""
from dataclasses import replace
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from yingxu.adapters.guessit_parser import GuessItParser
from yingxu.application.recognition import Recognition
from yingxu.application.reviewing import ReviewData
from yingxu.domain.releases import parse_release
from yingxu.domain.review import ReviewPlan
from yingxu.domain.matching import similarity


class ReleaseParserContracts(unittest.TestCase):
    def test_disabled_does_not_even_import_or_probe_library(self):
        with patch('yingxu.adapters.guessit_parser.version',side_effect=AssertionError('unexpected import')):
            self.assertEqual(GuessItParser().parse('Film.2024.mkv'),parse_release('Film.2024.mkv'))

    def test_missing_wrong_version_library_error_and_invalid_output_fall_back(self):
        name='Show.S01E01E02.1080p.mkv';baseline=parse_release(name)
        with patch('yingxu.adapters.guessit_parser.version',side_effect=PackageNotFoundError):
            value=GuessItParser(enabled=True).parse(name)
            self.assertEqual(value.episodes,baseline.episodes);self.assertEqual(value.parser,'builtin')
        for data in ({'title':'x'*257},{'episode':[1,True]},{'season':[1,2]},None):
            with self.subTest(data=data), patch('yingxu.adapters.guessit_parser.version',return_value='4.4.0'),patch(
                    'yingxu.adapters.guessit_parser.importlib.import_module',return_value=SimpleNamespace(guessit=lambda *_:data)):
                value=GuessItParser(enabled=True).parse(name)
                self.assertEqual(value.episodes,baseline.episodes);self.assertEqual(value.parser,'builtin')
        with patch('yingxu.adapters.guessit_parser.version',return_value='0.0'):
            self.assertEqual(GuessItParser(enabled=True).parse(name).parser,'builtin')

    def test_shadow_keeps_entire_episode_list_and_does_not_change_matching(self):
        with patch('yingxu.adapters.guessit_parser.version',return_value='4.4.0'),patch(
                'yingxu.adapters.guessit_parser.importlib.import_module',return_value=SimpleNamespace(
                    guessit=lambda *_:{'title':'Other title','episode':[1,2],'season':1,'type':'episode'})):
            parser=GuessItParser(enabled=True)
            self.assertEqual(parser.parse('Show.S01E01E02.mkv').episodes,(1,2))
            paths=[Path('Show.S01E01.mkv'),Path('Show.S01E01.en.srt')]
            before=similarity(*paths)
            plan=ReviewPlan([paths[0]],[paths[1]],exists=lambda p:False)
            data=ReviewData(plan,lambda p:p.name,recognition=Recognition(parser))
            self.assertEqual(similarity(*paths),before)
            self.assertTrue(any('未改变自动匹配' in text for text in data.rows[0]['basis']))

    def test_throwing_port_or_wrong_result_keeps_working_details(self):
        for parser in (SimpleNamespace(parse=lambda n:None),SimpleNamespace(parse=lambda n:1/0)):
            lines=Recognition(parser).lines('电影.2024.mkv')
            self.assertTrue(any('电影' in line for line in lines))
            self.assertIn('保留本地识别结果',lines[-1])


if __name__=='__main__':unittest.main()
