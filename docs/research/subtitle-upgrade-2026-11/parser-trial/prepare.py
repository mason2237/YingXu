import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

root=Path('work/tools/guessit-shadow')
target=root/'parser-libs';target.mkdir(exist_ok=True)
review=json.loads((root/'wheel-review.json').read_text())
for record in review:
    wheel=root/'wheels'/record['file']
    assert hashlib.sha256(wheel.read_bytes()).hexdigest()==record['sha256']
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            name=PurePosixPath(info.filename)
            assert not name.is_absolute() and '..' not in name.parts and '\\' not in info.filename
            assert not info.filename.endswith('.pth') and info.file_size<5*1024*1024
        # All wheels have been reviewed above. No setup, scripts or .pth run.
        archive.extractall(target)
replacement=root/'replacement-libs';(replacement/'guessit').mkdir(parents=True,exist_ok=True)
(replacement/'guessit/__init__.py').write_text("def guessit(name, options):\n    return {'title':'Replacement Library','type':'movie'}\n",encoding='utf-8')
(replacement/'guessit-4.4.0.dist-info').mkdir(exist_ok=True)
(replacement/'guessit-4.4.0.dist-info/METADATA').write_text('Metadata-Version: 2.1\nName: guessit\nVersion: 4.4.0\n',encoding='utf-8')
print('Prepared isolated replaceable library directories; runtime environment unchanged.')
