"""Generated 16x16 VP8 containers with subtitle tracks; no personal media.

The one black VP8 frame was encoded with Pillow 12.3.0. Container structures
are written here so tests need neither FFmpeg nor downloaded sample footage.
"""
import base64
import struct

FRAME = base64.b64decode("MAEAnQEqEAAQAAKAQiWkAANwAP745yAA")


def _vint(value):
    size = next(n for n in range(1, 9) if value < (1 << (7*n))-1)
    return (value | (1 << (7*size))).to_bytes(size, "big")


def _element(tag, value):
    tag = tag.to_bytes((tag.bit_length()+7)//8, "big")
    return tag + _vint(len(value)) + value


def _number(tag, value):
    return _element(tag, value.to_bytes(max(1, (value.bit_length()+7)//8), "big"))


def mkv(path, tracks=(), *, bitmap=False):
    """tracks: (ISO language, title, forced) tuples."""
    header = b"".join((_number(0x4286,1),_number(0x42F7,1),_number(0x42F2,4),_number(0x42F3,8),
                        _element(0x4282,b"matroska"),_number(0x4287,4),_number(0x4285,2)))
    info = _number(0x2AD7B1,1_000_000)+_element(0x4489,struct.pack('>d',2000))+_element(0x4D80,b"YingXu test")+_element(0x5741,b"YingXu test")
    video = _number(0xD7,1)+_number(0x73C5,1)+_number(0x83,1)+_element(0x86,b"V_VP8")+_number(0x23E383,2_000_000_000)
    video += _element(0xE0,_number(0xB0,16)+_number(0xBA,16))
    entries = _element(0xAE,video)
    cluster = _number(0xE7,0)+_element(0xA3,b'\x81\x00\x00\x80'+FRAME)
    for number,(language,title,forced) in enumerate(tracks,2):
        track = _number(0xD7,number)+_number(0x73C5,number)+_number(0x83,17)
        track += _element(0x86,b"S_HDMV/PGS" if bitmap else b"S_TEXT/UTF8")
        track += _element(0x22B59C,language.encode('ascii'))+_element(0x536E,title.encode('utf-8'))+_number(0x88,int(number==2))+_number(0x55AA,int(forced))
        entries += _element(0xAE,track)
        block = bytes((0x80|number,0,0,0))+('你好 / Hello' if language in {'zho','chi'} else 'Hello').encode('utf-8')
        cluster += _element(0xA0,_element(0xA1,block)+_number(0x9B,2000))
    data = _element(0x1A45DFA3,header)+_element(0x18538067,_element(0x1549A966,info)+_element(0x1654AE6B,entries)+_element(0x1F43B675,cluster))
    path.write_bytes(data)
    return path


def _box(kind, value=b''):
    return struct.pack('>I',len(value)+8)+kind.encode('ascii')+value


def _full(kind, value=b'', flags=0):
    return _box(kind,struct.pack('>I',flags)+value)


def mp4(path, language='eng'):
    """A two-second VP8 + tx3g MP4 fixture for track/language inspection."""
    matrix = struct.pack('>9I',0x10000,0,0,0,0x10000,0,0,0,0x40000000)
    def trak(number, text, offset, size):
        lang = sum((ord(c)-96) << shift for c,shift in zip(language if text else 'und',(10,5,0)))
        tkhd = _full('tkhd',struct.pack('>5I',0,0,number,0,2000)+b'\0'*8+struct.pack('>4H',0,0,0,0)+matrix+struct.pack('>2I',0 if text else 16<<16,0 if text else 16<<16),3)
        mdhd = _full('mdhd',struct.pack('>4I2H',0,0,1000,2000,lang,0))
        hdlr = _full('hdlr',b'\0'*4+(b'sbtl' if text else b'vide')+b'\0'*12+(b'SubtitleHandler' if text else b'VideoHandler')+b'\0')
        entry = b'\0'*6+struct.pack('>H',1)
        if text:
            entry = _box('tx3g',entry+b'\0'*30)
        else:
            entry += b'\0'*16+struct.pack('>2H2I',16,16,0x480000,0x480000)+b'\0'*4+struct.pack('>H',1)+b'\0'*32+struct.pack('>2H',24,0xffff)
            entry = _box('vp08',entry+_box('vpcC',b'\x01\x00\x00\x00\x00\x0a\x80\x01\x01\x01\x00\x00'))
        stbl = _full('stsd',struct.pack('>I',1)+entry)+_full('stts',struct.pack('>3I',1,1,2000))
        stbl += _full('stsc',struct.pack('>4I',1,1,1,1))+_full('stsz',struct.pack('>2I',size,1))+_full('stco',struct.pack('>2I',1,offset))
        dinf = _box('dinf',_full('dref',struct.pack('>I',1)+_full('url ',flags=1)))
        minf = _box('minf',(_full('nmhd') if text else _full('vmhd',b'\0'*8,1))+dinf+_box('stbl',stbl))
        return _box('trak',tkhd+_box('mdia',mdhd+hdlr+minf))
    ftyp = _box('ftyp',b'isom\0\0\x02\x00isommp42')
    text = b'\x00\x05Hello'
    mvhd = _full('mvhd',struct.pack('>4I',0,0,1000,2000)+struct.pack('>I',0x10000)+struct.pack('>H',0x100)+b'\0'*10+matrix+b'\0'*24+struct.pack('>I',3))
    moov = _box('moov',mvhd+trak(1,False,0,len(FRAME))+trak(2,True,0,len(text)))
    offset = len(ftyp)+len(moov)+8
    moov = _box('moov',mvhd+trak(1,False,offset,len(FRAME))+trak(2,True,offset+len(FRAME),len(text)))
    path.write_bytes(ftyp+moov+_box('mdat',FRAME+text))
    return path
