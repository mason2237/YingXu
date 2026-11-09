import struct
import unittest
from yingxu.domain.media_identity import BLOCK,MAX_NFO,opensubtitles_hash,parse_nfo


class MediaIdentityTests(unittest.TestCase):
    def test_hash_vectors_and_minimum(self):
        self.assertEqual(opensubtitles_hash(2*BLOCK,b'\0'*BLOCK,b'\0'*BLOCK),'0000000000020000')
        one=struct.pack('<Q',1)*(BLOCK//8)
        self.assertEqual(opensubtitles_hash(2*BLOCK,one,one),f'{2*BLOCK+2*(BLOCK//8):016x}')
        with self.assertRaises(ValueError):opensubtitles_hash(2*BLOCK-1,one,one)

    def test_type_conflicts_and_xml_entities(self):
        self.assertEqual(parse_nfo(b'<movie><uniqueid type="imdb">tt1234567</uniqueid></movie>')['ids'][0]['kind'],'movie')
        self.assertTrue(parse_nfo(b'<tvshow><id>tt1234567</id></tvshow>',episode=True)['conflict'])
        self.assertTrue(parse_nfo(b'<movie><id>tt1234567</id><id>tt1234568</id></movie>')['conflict'])
        for raw in (b'<!DOCTYPE movie [<!ENTITY x SYSTEM "file:///private">]><movie/>',b'x'*(MAX_NFO+1),b'<movie>'):
            with self.subTest(raw=raw[:50]),self.assertRaises(ValueError):parse_nfo(raw)
