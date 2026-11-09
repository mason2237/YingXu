"""Identity ambiguity and subtitle purpose must survive parsing and planning."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from yingxu.domain.releases import parse_release
from yingxu.domain.review import ReviewPlan
from yingxu.domain.planning import destination_for
from yingxu.domain.subtitle_variants import split_variant, variant_of


class ReleaseMetadataTests(unittest.TestCase):
    def test_movie_remake_year_source_group_and_cut(self):
        original=parse_release('The.Movie.1984.1080p.BluRay.REMUX.EXTENDED.x264-GROUP.mkv')
        remake=parse_release('The.Movie.2024.2160p.WEB-DL.x265-TEAM.mkv')
        self.assertEqual((original.title,original.year,original.source,original.release_group),('The Movie',1984,'BluRay','group'))
        self.assertTrue(original.remux);self.assertEqual(original.edition,('extended',))
        self.assertEqual((remake.year,remake.source),(2024,'WEB-DL'))
        self.assertEqual(parse_release('1917.2019.1080p.BluRay.mkv').title,'1917')
        self.assertEqual(parse_release('2001.A.Space.Odyssey.1968.mkv').year,1968)
        self.assertEqual(parse_release('Spider-Man.mkv').title,'Spider-Man')
        for source in ('WEBRip','DVD'):
            self.assertEqual(parse_release(f'Movie.2024.{source}.mkv').source,source)
        self.assertEqual(parse_release('Movie_2024_DIRECTORS_CUT_WEB-DL.mkv').edition,('directors-cut',))

    def test_multi_episode_chinese_special_date_and_absolute(self):
        value=parse_release('Show.S02E01-E03.1080p.HDTV-GROUP.mkv')
        self.assertEqual((value.season,value.episodes,value.numbering),(2,(1,2,3),'season_episode'))
        self.assertEqual(value.source,'HDTV')
        self.assertEqual(parse_release('剧名.第二季.第十二集.mkv').episodes,(12,))
        self.assertEqual(parse_release('剧名.第二季.第十二集.mkv').season,2)
        self.assertEqual(parse_release('Series.SP01.1080p.mkv').special,'SP01')
        self.assertEqual(parse_release('News.2024.02.29.HDTV.mkv').air_date,'2024-02-29')
        self.assertIsNone(parse_release('News.2023.02.29.mkv').air_date)
        self.assertIsNone(parse_release('News.2023.02.29.mkv').year)
        self.assertFalse(parse_release('News.2023.02.29.mkv').complete)
        absolute=parse_release('[Fansub] Anime Title - 012v2 [1080p].mkv')
        self.assertEqual((absolute.title,absolute.episodes,absolute.numbering),('Anime Title',(12,),'absolute'))
        self.assertEqual(parse_release('Movie.2024.1080p.mkv').episodes,())
        self.assertFalse(parse_release('Show.S01E03-E01.mkv').complete)

    def test_unknown_and_oversized_fields_are_explicit_and_immutable(self):
        value=parse_release('Untitled.mkv')
        self.assertIsNone(value.year);self.assertEqual(value.kind,'unknown')
        self.assertEqual(value.origin,'filename');self.assertEqual(value.parser,'builtin')
        with self.assertRaises(FrozenInstanceError):value.title='changed'
        for name in ('x'*3000,'a\x00b',None):
            with self.subTest(name=str(name)[:30]):
                self.assertFalse(parse_release(name).complete)
                self.assertIsNone(parse_release(name).title)
        self.assertEqual(parse_release('Other.Movie/Actual.Title.2024.mkv').title,'Actual Title')

    def test_language_aliases_script_and_purpose_have_separate_keys(self):
        key=lambda tag:variant_of(Path('Film.'+tag+'.srt'))
        self.assertEqual(key('chs').key,key('zh-Hans').key)
        self.assertEqual(key('chs').key,key('zh-cn').key)
        self.assertEqual(key('eng').key,key('en').key)
        self.assertNotEqual(key('zh-Hans').key,key('zh-Hant').key)
        self.assertEqual(key('zh-cn').region,'CN')
        self.assertEqual(key('zh-Hans').region,'')
        self.assertNotEqual(key('en-US').key,key('en-GB').key)
        self.assertIn('US',key('en-US').label)
        self.assertNotEqual(key('en').key,key('en.forced').key)
        self.assertNotEqual(key('en').key,key('en.sdh').key)
        self.assertNotEqual(key('en.forced').key,key('en.sdh').key)
        self.assertEqual(key('en.HI').key,key('en.sdh').key)
        self.assertTrue(key('en.commentary').commentary)
        self.assertEqual(key('chs.eng').languages,('en','zh'))
        self.assertTrue(key('chs.cht').ambiguous)
        self.assertEqual(split_variant('My.english.Title')[0],'My.english.Title')

    def test_variants_coexist_and_duplicate_requires_explicit_replacement(self):
        video=Path('Film.S01E01.mkv')
        subtitles=[Path('Film.S01E01.'+tag+'.srt') for tag in ('en','en.forced','en.sdh','chs','cht')]
        plan=ReviewPlan([video],subtitles,exists=lambda p:False)
        self.assertEqual(len(plan.rows[0].matches),5)
        self.assertEqual(len({match.target for match in plan.rows[0].matches}),5)
        for subtitle in subtitles:
            self.assertEqual(destination_for(video,subtitle,set(),exists=lambda p:False),subtitle)
        other=Path('Film.S01E01.eng.srt')
        plan=ReviewPlan([video],[*subtitles,other],exists=lambda p:False)
        self.assertEqual(len(plan.rows[0].matches),5)
        english=next(m.source for m in plan.rows[0].matches if variant_of(m.source).key==variant_of(other).key)
        replacement=other if english!=other else subtitles[0]
        with self.assertRaisesRegex(ValueError,'用途'):plan.assign(0,replacement)
        plan.assign(0,replacement,english)
        self.assertEqual(len(plan.rows[0].matches),5)
        self.assertEqual(plan.state(0),'需确认')

    def test_purpose_survives_target_conflict_numbering(self):
        video=Path('Film.mkv');subtitle=Path('Other.en.forced.srt')
        result=destination_for(video,subtitle,set(),exists=lambda p:p.name=='Film.en.forced.srt')
        self.assertEqual(result.name,'Film_1.en.forced.srt')


if __name__=='__main__':unittest.main()
