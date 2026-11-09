import random
import unittest
from yingxu.domain.subtitle_document import parse_document
from yingxu.domain.content_matching import features,compare
from yingxu.domain.matching import ScanCancelled


def document(seed=8,intro_only=False):
    rng=random.Random(seed);words=['river','mountain','quiet','journey','distant','garden','morning','memory','stranger','forest','letter','window','station','cloud','friend','secret','summer','house','lantern','voice']
    rows=[]
    for i in range(60):
        text=' '.join(rng.sample(words,8))+f' scene {i}'
        if intro_only and i>=20:text='sing again sing again'
        rows.append(f'{i+1}\n00:{i//10:02}:{i%10*5:02},000 --> 00:{i//10:02}:{i%10*5+3:02},000\n{text}\n')
    return parse_document('\n'.join(rows),'srt')


class ContentEvidenceTests(unittest.TestCase):
    def test_full_same_episode_supports_but_intro_or_short_never_does(self):
        reference=features(document());self.assertEqual(compare(reference,features(document()))['status'],'supporting')
        self.assertEqual(compare(reference,features(document(intro_only=True)))['status'],'insufficient_evidence')
        self.assertEqual(compare(reference,features(document()),False)['status'],'insufficient_evidence')
        short=features(parse_document('1\n00:00:01,000 --> 00:00:02,000\nOnly tiny text\n','srt'))
        self.assertEqual(compare(reference,short)['status'],'insufficient_evidence')

    def test_same_vocabulary_different_episode_is_not_supporting_and_cancel_works(self):
        self.assertEqual(compare(features(document(8)),features(document(9)))['status'],'ambiguous')
        with self.assertRaises(ScanCancelled):features(document(),lambda:True)
