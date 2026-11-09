"""Generated-sample packaging probe; not a desktop host or file operation tool."""
import json
from pathlib import Path
import sys

base=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
directory=Path(sys.argv[1]) if len(sys.argv)>1 else base/'parser-libs'
sys.path.insert(0,str(directory))
if not getattr(sys,'frozen',False):sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from yingxu.adapters.guessit_parser import GuessItParser

if '--diagnose' in sys.argv:
    from guessit import guessit
    print(guessit('The.Movie.2024.1080p.WEB-DL.mkv',{'name_only':True,'no_user_config':True}))

parser=GuessItParser(enabled=True)
names=('The.Movie.2024.1080p.WEB-DL.x265-GROUP.mkv','Series.S01E01E02.mkv')
print(json.dumps([{'input':name,'parser':(result:=parser.parse(name)).parser,
    'version':result.parser_version,'title':result.title,'episodes':result.episodes,
    'warnings':result.warnings} for name in names],ensure_ascii=True))
