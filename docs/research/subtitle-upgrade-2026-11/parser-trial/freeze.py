import ast
from pathlib import Path
import subprocess
import sys

base=Path('work/tools/guessit-shadow')
modules=set()
for file in (base/'parser-libs').rglob('*.py'):
    if any(part in {'test','tests'} for part in file.parts):continue
    for node in ast.walk(ast.parse(file.read_text(encoding='utf-8-sig'))):
        names=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) and not node.level else []
        for name in names:
            if name.split('.')[0] in sys.stdlib_module_names:modules.add(name)
assert not any(name.startswith(('tkinter','PySide','PyQt')) for name in modules)
command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--console','--name','ParserProbe',
    '--distpath',str(base/'frozen'),'--workpath','work/build/guessit-shadow','--specpath','work/build/guessit-shadow','--paths','.']
for package in ('guessit','rebulk','babelfish','dateutil','tzdata'):command+=['--exclude-module',package]
for name in sorted(modules):command+=['--hidden-import',name]
command += [str(base/'probe.py')]
(base/'stdlib-imports.txt').write_text('\n'.join(sorted(modules))+'\n',encoding='utf-8')
raise SystemExit(subprocess.call(command))
